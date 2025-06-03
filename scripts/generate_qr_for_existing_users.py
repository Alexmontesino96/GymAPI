#!/usr/bin/env python3
"""
Script para generar códigos QR para usuarios existentes que no tienen QR asignado.

Este script debe ejecutarse una sola vez después de implementar el sistema de QR
para asegurar que todos los usuarios existentes tengan su código QR único.

Uso:
    python scripts/generate_qr_for_existing_users.py
"""

import sys
import os
from pathlib import Path

# Añadir el directorio raíz del proyecto al Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.services.attendance import attendance_service
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def generate_qr_for_existing_users():
    """
    Genera códigos QR para usuarios existentes que no tienen QR asignado.
    """
    logger.info("Iniciando generación de códigos QR para usuarios existentes...")
    
    # Obtener sesión de base de datos
    db_session = next(get_db())
    
    try:
        # Buscar usuarios sin código QR
        users_without_qr = db_session.query(User).filter(
            (User.qr_code == None) | (User.qr_code == "")
        ).all()
        
        logger.info(f"Encontrados {len(users_without_qr)} usuarios sin código QR")
        
        if not users_without_qr:
            logger.info("Todos los usuarios ya tienen código QR asignado")
            return
        
        # Procesar cada usuario
        updated_count = 0
        errors = []
        
        for user in users_without_qr:
            try:
                # Generar código QR único
                qr_code = await attendance_service.generate_qr_code(user.id)
                
                # Verificar que el QR no esté duplicado
                existing_qr = db_session.query(User).filter(
                    User.qr_code == qr_code,
                    User.id != user.id
                ).first()
                
                if existing_qr:
                    logger.warning(f"QR duplicado generado para usuario {user.id}, regenerando...")
                    # Regenerar hasta obtener uno único
                    attempts = 0
                    while existing_qr and attempts < 10:
                        qr_code = await attendance_service.generate_qr_code(user.id)
                        existing_qr = db_session.query(User).filter(
                            User.qr_code == qr_code,
                            User.id != user.id
                        ).first()
                        attempts += 1
                    
                    if attempts >= 10:
                        raise Exception(f"No se pudo generar QR único para usuario {user.id}")
                
                # Asignar QR al usuario
                user.qr_code = qr_code
                db_session.add(user)
                
                updated_count += 1
                logger.info(f"QR generado para usuario {user.id} ({user.email}): {qr_code}")
                
            except Exception as e:
                error_msg = f"Error generando QR para usuario {user.id} ({user.email}): {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Confirmar cambios
        if updated_count > 0:
            db_session.commit()
            logger.info(f"✅ Códigos QR generados exitosamente para {updated_count} usuarios")
        
        # Reportar errores si los hay
        if errors:
            logger.error(f"❌ Se encontraron {len(errors)} errores:")
            for error in errors:
                logger.error(f"  - {error}")
        
        # Verificar resultados
        remaining_without_qr = db_session.query(User).filter(
            (User.qr_code == None) | (User.qr_code == "")
        ).count()
        
        if remaining_without_qr == 0:
            logger.info("🎉 Todos los usuarios tienen ahora código QR asignado")
        else:
            logger.warning(f"⚠️  Quedan {remaining_without_qr} usuarios sin código QR")
            
    except Exception as e:
        logger.error(f"Error crítico en el proceso: {str(e)}")
        db_session.rollback()
        raise
    finally:
        db_session.close()


async def verify_qr_uniqueness():
    """
    Verifica que todos los códigos QR sean únicos.
    """
    logger.info("Verificando unicidad de códigos QR...")
    
    db_session = next(get_db())
    
    try:
        # Buscar QRs duplicados
        from sqlalchemy import func
        duplicates = db_session.query(
            User.qr_code, func.count(User.id).label('count')
        ).filter(
            User.qr_code != None,
            User.qr_code != ""
        ).group_by(User.qr_code).having(func.count(User.id) > 1).all()
        
        if duplicates:
            logger.error(f"❌ Se encontraron {len(duplicates)} códigos QR duplicados:")
            for qr_code, count in duplicates:
                users_with_qr = db_session.query(User).filter(User.qr_code == qr_code).all()
                logger.error(f"  QR '{qr_code}' usado por {count} usuarios:")
                for user in users_with_qr:
                    logger.error(f"    - Usuario {user.id} ({user.email})")
            return False
        else:
            logger.info("✅ Todos los códigos QR son únicos")
            return True
            
    except Exception as e:
        logger.error(f"Error verificando unicidad: {str(e)}")
        return False
    finally:
        db_session.close()


async def show_qr_stats():
    """
    Muestra estadísticas de códigos QR en la base de datos.
    """
    logger.info("Generando estadísticas de códigos QR...")
    
    db_session = next(get_db())
    
    try:
        total_users = db_session.query(User).count()
        users_with_qr = db_session.query(User).filter(
            User.qr_code != None,
            User.qr_code != ""
        ).count()
        users_without_qr = total_users - users_with_qr
        
        logger.info("📊 Estadísticas de códigos QR:")
        logger.info(f"  Total de usuarios: {total_users}")
        logger.info(f"  Usuarios con QR: {users_with_qr}")
        logger.info(f"  Usuarios sin QR: {users_without_qr}")
        
        if total_users > 0:
            percentage = (users_with_qr / total_users) * 100
            logger.info(f"  Porcentaje con QR: {percentage:.1f}%")
            
    except Exception as e:
        logger.error(f"Error generando estadísticas: {str(e)}")
    finally:
        db_session.close()


async def main():
    """
    Función principal del script.
    """
    logger.info("=== Script de generación de códigos QR para usuarios existentes ===")
    
    try:
        # Mostrar estadísticas iniciales
        await show_qr_stats()
        
        # Generar códigos QR para usuarios sin QR
        await generate_qr_for_existing_users()
        
        # Verificar unicidad
        await verify_qr_uniqueness()
        
        # Mostrar estadísticas finales
        await show_qr_stats()
        
        logger.info("=== Script completado exitosamente ===")
        
    except Exception as e:
        logger.error(f"Error ejecutando script: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 