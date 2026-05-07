from app.services.bootstrap_service import BootstrapService


if __name__ == "__main__":
    BootstrapService.initialize()
    print("Database tables created successfully.")
