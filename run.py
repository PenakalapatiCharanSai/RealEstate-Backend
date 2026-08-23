
from app import create_app
from app.config.config import Config

app = create_app()

if __name__ == "__main__":
    port = Config.PORT
    debug = Config.FLASK_ENV == "development"
    print(f"Starting Real Estate Marketplace API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=debug)
