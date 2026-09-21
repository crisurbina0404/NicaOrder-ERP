<img width="1919" height="905" alt="image" src="https://github.com/user-attachments/assets/25de4a58-3a73-48e2-bede-e8509c996c3e" />

# NicaOrder

Sistema de gestion empresarial para una tienda de productos medicos en Nicaragua.

## Tecnologia

- Python
- Flask
- SQLite
- SQLAlchemy
- Jinja2
- HTML, CSS, JavaScript

## Estructura del proyecto

```
app/
├── __init__.py
├── config.py
├── extensions.py
├── models/
├── routes/
├── services/
├── templates/
└── static/
    ├── css/
    ├── js/
    └── images/
instance/
tests/
run.py
requirements.txt
```

## Instalacion

1. Crear un entorno virtual:

   ```
   python -m venv venv
   ```

2. Activar el entorno virtual:

   - Windows (PowerShell):

     ```
     venv\Scripts\Activate.ps1
     ```

   - Windows (cmd):

     ```
     venv\Scripts\activate
     ```

3. Instalar dependencias:

   ```
   pip install -r requirements.txt
   ```

## Ejecucion

Dentro del entorno virtual, ejecutar:

```
python run.py
```

Luego abrir en el navegador:

```
http://127.0.0.1:5000/
```

La base de datos SQLite se crea automaticamente en `instance/nicaorder.db`.
