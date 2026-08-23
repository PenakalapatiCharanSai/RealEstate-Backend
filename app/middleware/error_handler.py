from flask import jsonify

def register_error_handlers(app):
    @app.errorhandler(400)
    def handle_400_error(error):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": getattr(error, "description", "Invalid request parameters.")
        }), 400

    @app.errorhandler(401)
    def handle_401_error(error):
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": getattr(error, "description", "Authentication required to access this resource.")
        }), 401

    @app.errorhandler(403)
    def handle_403_error(error):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": getattr(error, "description", "You do not have permission to perform this operation.")
        }), 403

    @app.errorhandler(404)
    def handle_404_error(error):
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "The requested resource or endpoint does not exist."
        }), 404

    @app.errorhandler(405)
    def handle_405_error(error):
        return jsonify({
            "success": False,
            "error": "Method Not Allowed",
            "message": "The HTTP method is not supported for this endpoint."
        }), 405

    @app.errorhandler(500)
    def handle_500_error(error):
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred. Please try again later."
        }), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Format unhandled exceptions gracefully as JSON without exposing stack traces
        response = {
            "success": False,
            "error": "Server Error",
            "message": str(error) if app.config.get("FLASK_ENV") == "development" else "An unexpected error occurred."
        }
        return jsonify(response), 500
