import importlib
import subprocess
import sys
import logging
logger = logging.getLogger("Dependency Checker")


REQUIRED_PACKAGES = [
    'PyJWT',
    'httpx',
    'uuid',
    'aiofiles',
    'packaging',
    'json5',
    'aiohttp',
    'requests',
    'tenacity'
    ]


def install_package(package):
    """Install a package using pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
def check_dependencies():
    """Check if all required packages are installed."""
    missing_packages = []
    for package in REQUIRED_PACKAGES:
        try:
            importlib.import_module(package.split('>')[0].split('<')[0].split('=')[0])
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.info(f"Installing missing dependencies: {', '.join(missing_packages)}")
        for package in missing_packages:
            try:
                install_package(package)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {package}: {e}")
                sys.exit(1)

check_dependencies()