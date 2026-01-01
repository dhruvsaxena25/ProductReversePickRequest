import os

PROJECT_STRUCTURE = {
    "app": {
        "__init__.py": None,
        "main.py": None,
        "config": {
            "__init__.py": None,
            "settings.py": None,
        },
        "core": {
            "__init__.py": None,
            "exceptions.py": None,
            "security.py": None,
            "dependencies.py": None,
        },
        "db": {
            "__init__.py": None,
            "database.py": None,
            "models.py": None,
            "init_db.py": None,
        },
        "schemas": {
            "__init__.py": None,
            "auth.py": None,
            "user.py": None,
            "pick_request.py": None,
            "common.py": None,
        },
        "services": {
            "__init__.py": None,
            "auth_service.py": None,
            "user_service.py": None,
            "pick_request_service.py": None,
            "cleanup_service.py": None,
        },
        "api": {
            "__init__.py": None,
            "router.py": None,
            "v1": {
                "__init__.py": None,
                "auth.py": None,
                "users.py": None,
                "pick_requests.py": None,
                "products.py": None,
                "health.py": None,
            },
        },
        "websockets": {
            "__init__.py": None,
            "scanner.py": None,
            "picker.py": None,
        },
        "scanner": {
            "__init__.py": None,
            "core.py": None,
        },
        "catalog": {
            "__init__.py": None,
            "models.py": None,
            "catalog.py": None,
        },
        "utils": {
            "__init__.py": None,
            "pick_logger.py": None,
            "validators.py": None,
        },
    },
    "data": {
        "products.json": None,
    },
    "storage": {
        "db": {
            ".gitkeep": None,
        },
        "logs": {
            ".gitkeep": None,
        },
    },
    "static": {
        "frontend": {
            "index.html": None,
            "api-home.html": None,
        }
    },
    "tests": {
        "__init__.py": None,
        "conftest.py": None,
        "test_auth.py": None,
        "test_users.py": None,
        "test_pick_requests.py": None,
        "test_scanner.py": None,
    },
    "docker": {
        "Dockerfile": None,
        "docker-compose.yml": None,
    },
    ".env.example": None,
    ".gitignore": None,
    "requirements.txt": None,
    "requirements-dev.txt": None,
    "README.md": None,
}


def create_structure(base_path, structure):
    for name, content in structure.items():
        path = os.path.join(base_path, name)

        if content is None:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8"):
                    pass
                print(f"Created file: {path}")
        else:
            os.makedirs(path, exist_ok=True)
            print(f"Created directory: {path}")
            create_structure(path, content)


if __name__ == "__main__":
    ROOT_DIR = os.getcwd()
    create_structure(ROOT_DIR, PROJECT_STRUCTURE)
    print("\nProject structure generated successfully.")
