#!/usr/bin/env python3
"""
Script para configurar las colas SQS de notificaciones de nutrición.

Este script crea:
1. Cola principal de notificaciones
2. Dead Letter Queue (DLQ) para mensajes fallidos
3. Configura la política de reintentos

Uso:
    python scripts/setup_sqs_queues.py

Requisitos:
    - AWS CLI configurado o variables de entorno AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY
    - Permisos para crear colas SQS

Variables de entorno opcionales:
    - AWS_REGION: Región de AWS (default: us-east-1)
    - SQS_QUEUE_NAME: Nombre de la cola (default: gymapi-nutrition-notifications)
"""

import argparse
import boto3
import json
import os
import sys

# Configuración por defecto
DEFAULT_REGION = "us-east-1"
DEFAULT_QUEUE_NAME = "gymapi-nutrition-notifications"
DEFAULT_DLQ_NAME = "gymapi-nutrition-notifications-dlq"


def get_sqs_client(region: str):
    """Crear cliente SQS de boto3"""
    return boto3.client(
        'sqs',
        region_name=region,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )


def create_dlq(sqs_client, dlq_name: str, region: str) -> str:
    """
    Crear la Dead Letter Queue.

    Returns:
        ARN de la DLQ
    """
    print(f"Creating Dead Letter Queue: {dlq_name}...")

    # Atributos de la DLQ
    dlq_attributes = {
        # Retención de mensajes: 14 días (máximo)
        'MessageRetentionPeriod': '1209600',
        # Visibilidad: 30 segundos
        'VisibilityTimeout': '30',
        # Delay: 0 segundos
        'DelaySeconds': '0'
    }

    try:
        response = sqs_client.create_queue(
            QueueName=dlq_name,
            Attributes=dlq_attributes
        )
        dlq_url = response['QueueUrl']
        print(f"  DLQ URL: {dlq_url}")

        # Obtener el ARN de la DLQ
        attrs = sqs_client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=['QueueArn']
        )
        dlq_arn = attrs['Attributes']['QueueArn']
        print(f"  DLQ ARN: {dlq_arn}")

        return dlq_arn, dlq_url

    except sqs_client.exceptions.QueueNameExists:
        print(f"  DLQ already exists, getting ARN...")
        dlq_url = sqs_client.get_queue_url(QueueName=dlq_name)['QueueUrl']
        attrs = sqs_client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=['QueueArn']
        )
        dlq_arn = attrs['Attributes']['QueueArn']
        print(f"  Existing DLQ ARN: {dlq_arn}")
        return dlq_arn, dlq_url


def create_main_queue(sqs_client, queue_name: str, dlq_arn: str) -> str:
    """
    Crear la cola principal de notificaciones.

    Returns:
        URL de la cola
    """
    print(f"Creating main queue: {queue_name}...")

    # Política de redirección a DLQ después de 3 intentos fallidos
    redrive_policy = {
        "deadLetterTargetArn": dlq_arn,
        "maxReceiveCount": "3"  # Después de 3 intentos fallidos, ir a DLQ
    }

    # Atributos de la cola principal
    queue_attributes = {
        # Tiempo de visibilidad: 60 segundos (tiempo para procesar)
        'VisibilityTimeout': '60',
        # Retención de mensajes: 4 días
        'MessageRetentionPeriod': '345600',
        # Delay: 0 segundos (sin delay)
        'DelaySeconds': '0',
        # Tamaño máximo de mensaje: 256 KB
        'MaximumMessageSize': '262144',
        # Long polling: 20 segundos
        'ReceiveMessageWaitTimeSeconds': '20',
        # Política de redirección a DLQ
        'RedrivePolicy': json.dumps(redrive_policy)
    }

    try:
        response = sqs_client.create_queue(
            QueueName=queue_name,
            Attributes=queue_attributes
        )
        queue_url = response['QueueUrl']
        print(f"  Queue URL: {queue_url}")
        return queue_url

    except sqs_client.exceptions.QueueNameExists:
        print(f"  Queue already exists, updating attributes...")
        queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
        sqs_client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes=queue_attributes
        )
        print(f"  Existing Queue URL: {queue_url}")
        return queue_url


def print_env_config(queue_url: str, dlq_url: str, region: str):
    """Imprimir configuración para .env"""
    print("\n" + "=" * 60)
    print("CONFIGURACIÓN PARA .env")
    print("=" * 60)
    print(f"""
# AWS SQS Configuration for Nutrition Notifications
AWS_REGION={region}
SQS_NUTRITION_QUEUE_URL={queue_url}
SQS_NUTRITION_DLQ_URL={dlq_url}

# AWS Credentials (si no usas IAM roles)
# AWS_ACCESS_KEY_ID=tu_access_key
# AWS_SECRET_ACCESS_KEY=tu_secret_key
""")
    print("=" * 60)


def verify_queues(sqs_client, queue_url: str, dlq_url: str):
    """Verificar que las colas estén funcionando"""
    print("\nVerifying queues...")

    # Verificar cola principal
    try:
        attrs = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        )
        print(f"  Main queue attributes:")
        print(f"    - VisibilityTimeout: {attrs['Attributes'].get('VisibilityTimeout')}s")
        print(f"    - MessageRetentionPeriod: {int(attrs['Attributes'].get('MessageRetentionPeriod', 0)) // 86400} days")
        print(f"    - ReceiveMessageWaitTimeSeconds: {attrs['Attributes'].get('ReceiveMessageWaitTimeSeconds')}s")
        print(f"    - ApproximateNumberOfMessages: {attrs['Attributes'].get('ApproximateNumberOfMessages', 0)}")
        print("  Main queue: OK")
    except Exception as e:
        print(f"  Error verifying main queue: {e}")
        return False

    # Verificar DLQ
    try:
        attrs = sqs_client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=['ApproximateNumberOfMessages']
        )
        print(f"  DLQ messages: {attrs['Attributes'].get('ApproximateNumberOfMessages', 0)}")
        print("  DLQ: OK")
    except Exception as e:
        print(f"  Error verifying DLQ: {e}")
        return False

    print("\nAll queues verified successfully!")
    return True


def send_test_message(sqs_client, queue_url: str):
    """Enviar mensaje de prueba"""
    print("\nSending test message...")

    test_message = {
        "message_type": "test",
        "user_id": 0,
        "gym_id": 0,
        "title": "Test Notification",
        "body": "This is a test message from setup script",
        "data": {"test": True}
    }

    try:
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(test_message),
            MessageAttributes={
                'MessageType': {
                    'DataType': 'String',
                    'StringValue': 'test'
                }
            }
        )
        print(f"  Test message sent! MessageId: {response['MessageId']}")

        # Recibir y eliminar el mensaje de prueba
        print("  Receiving test message...")
        receive_response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5
        )

        if 'Messages' in receive_response:
            msg = receive_response['Messages'][0]
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=msg['ReceiptHandle']
            )
            print("  Test message received and deleted successfully!")
        else:
            print("  Warning: Could not receive test message")

        return True

    except Exception as e:
        print(f"  Error in test: {e}")
        return False


def delete_queues(sqs_client, queue_name: str, dlq_name: str):
    """Eliminar las colas (para cleanup)"""
    print(f"Deleting queues...")

    try:
        queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
        sqs_client.delete_queue(QueueUrl=queue_url)
        print(f"  Deleted: {queue_name}")
    except Exception as e:
        print(f"  Could not delete {queue_name}: {e}")

    try:
        dlq_url = sqs_client.get_queue_url(QueueName=dlq_name)['QueueUrl']
        sqs_client.delete_queue(QueueUrl=dlq_url)
        print(f"  Deleted: {dlq_name}")
    except Exception as e:
        print(f"  Could not delete {dlq_name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Setup SQS queues for nutrition notifications'
    )
    parser.add_argument(
        '--region', '-r',
        default=os.environ.get('AWS_REGION', DEFAULT_REGION),
        help=f'AWS region (default: {DEFAULT_REGION})'
    )
    parser.add_argument(
        '--queue-name', '-q',
        default=DEFAULT_QUEUE_NAME,
        help=f'Main queue name (default: {DEFAULT_QUEUE_NAME})'
    )
    parser.add_argument(
        '--dlq-name', '-d',
        default=DEFAULT_DLQ_NAME,
        help=f'DLQ name (default: {DEFAULT_DLQ_NAME})'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Send a test message after setup'
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Delete queues instead of creating them (DANGER!)'
    )

    args = parser.parse_args()

    # Verificar credenciales
    if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
        print("Warning: AWS credentials not found in environment variables.")
        print("Make sure you have AWS CLI configured or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print()

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║     SQS Queue Setup for Nutrition Notifications           ║
╚═══════════════════════════════════════════════════════════╝

Region: {args.region}
Queue Name: {args.queue_name}
DLQ Name: {args.dlq_name}
""")

    try:
        sqs_client = get_sqs_client(args.region)

        if args.delete:
            confirm = input("Are you sure you want to delete the queues? (yes/no): ")
            if confirm.lower() == 'yes':
                delete_queues(sqs_client, args.queue_name, args.dlq_name)
            else:
                print("Aborted.")
            return

        # Crear DLQ primero
        dlq_arn, dlq_url = create_dlq(sqs_client, args.dlq_name, args.region)

        # Crear cola principal
        queue_url = create_main_queue(sqs_client, args.queue_name, dlq_arn)

        # Verificar
        if not verify_queues(sqs_client, queue_url, dlq_url):
            sys.exit(1)

        # Test opcional
        if args.test:
            if not send_test_message(sqs_client, queue_url):
                print("Warning: Test message failed, but queues were created.")

        # Imprimir configuración
        print_env_config(queue_url, dlq_url, args.region)

        print("\nSetup completed successfully!")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
