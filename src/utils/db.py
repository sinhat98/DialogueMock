import os
import aiohttp
from flask_marshmallow import Marshmallow
from sqlalchemy.ext.declarative import declarative_base

from src.utils.gcp import CloudSQL as CloudSQLDriver

from dotenv import load_dotenv

load_dotenv()

ma = Marshmallow()
Base = declarative_base()

db_setting = {
    "env": os.environ["ENV"],
    "project_id": os.environ["GCP_PROJECT_ID"],
    "protocol": os.environ["MYSQL_PROTOCOL"],
    "db_user": os.environ["MYSQL_USER"],
    "db_pass": os.environ["MYSQL_PASSWORD"],
    "host": os.environ["MYSQL_ADDRESS"],
    "port": os.environ["MYSQL_PORT"],
}
csqld = CloudSQLDriver(**db_setting)
session = aiohttp.ClientSession()

