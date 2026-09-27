from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connections


class Command(BaseCommand):
    help = (
        "Check that the database is reachable. On PostgreSQL, create the database "
        "itself if the server is reachable but the database doesn't exist yet."
    )

    def handle(self, *args, **options):
        connection = connections["default"]
        try:
            connection.ensure_connection()
        except OperationalError as exc:
            name = connection.settings_dict["NAME"]
            if connection.vendor != "postgresql" or "does not exist" not in str(exc):
                raise CommandError(f"Can't connect to the database: {exc}")
            self.stdout.write(f"    database {name} doesn't exist yet, creating it")
            try:
                # Connects to the server's maintenance database with the same credentials.
                with connection._nodb_cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE {connection.ops.quote_name(name)}")
            except Exception as create_exc:
                raise CommandError(
                    f"Couldn't create database {name}: {create_exc}. Create it yourself "
                    f"(CREATE DATABASE {name};) or give DB_USER the CREATEDB privilege."
                )
            connection.close()
            connection.ensure_connection()

        settings = connection.settings_dict
        if connection.vendor == "sqlite":
            where = str(settings["NAME"])
        else:
            where = f"{settings['USER']}@{settings['HOST']}:{settings['PORT']}/{settings['NAME']}"
        self.stdout.write(f"    {connection.vendor}: {where}")
