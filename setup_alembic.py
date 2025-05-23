import os
import sys

def setup_alembic():
    """Create necessary directories for Alembic migrations."""
    try:
        # Create versions directory if it doesn't exist
        versions_dir = os.path.join('alembic', 'versions')
        if not os.path.exists(versions_dir):
            os.makedirs(versions_dir)
            print(f"Created directory: {versions_dir}")
        else:
            print(f"Directory already exists: {versions_dir}")
        
        # Make sure it's writable by setting permissions
        os.chmod(versions_dir, 0o777)
        print(f"Set permissions on {versions_dir}")
        
        return 0
    except Exception as e:
        print(f"Error setting up Alembic: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(setup_alembic())
