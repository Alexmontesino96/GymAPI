#!/bin/bash

# Script para ejecutar los tests

echo "Ejecutando tests para la API GymAPI"
echo "-----------------------------------"

# Asegurarse de que estamos usando el entorno virtual
if [ -d "env" ]; then
    if [ -f "env/bin/activate" ]; then
        source env/bin/activate
    elif [ -f "env/Scripts/activate" ]; then
        source env/Scripts/activate
    fi
fi

# Ejecutar los tests con pytest
pytest -v tests/

echo "-----------------------------------"
echo "Finalización de tests" 