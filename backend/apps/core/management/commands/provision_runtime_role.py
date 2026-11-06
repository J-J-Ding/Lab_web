"""Explicit server-only role provisioning; passwords accepted only from environment."""
import os
from django.core.management.base import BaseCommand,CommandError
from django.db import connection,transaction
from psycopg import sql
class Command(BaseCommand):
    help='Provision a nonsuperuser runtime role using LAB_RUNTIME_DB_USER/PASSWORD environment.'
    def handle(self,*args,**o):
        user=os.environ.get('LAB_RUNTIME_DB_USER','');password=os.environ.get('LAB_RUNTIME_DB_PASSWORD','')
        if not user or not user.replace('_','').isalnum() or len(password)<32:raise CommandError('Valid role and >=32 character environment password required')
        with transaction.atomic(),connection.cursor() as c:
            c.execute('SELECT current_user,current_database()');admin,database=c.fetchone()
            if user==admin:raise CommandError('Runtime role must differ from provisioning role')
            c.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')
            if not c.fetchone()[0]:raise CommandError('Provision using the server migration/DB administrator')
            c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',[user]);exists=c.fetchone()
            action='ALTER' if exists else 'CREATE'
            c.execute(sql.SQL(action+' ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}').format(sql.Identifier(user),sql.Literal(password)))
            c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database),sql.Identifier(user)))
            c.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(user)))
            c.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(user)))
            c.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(user)))
            c.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {}').format(sql.Identifier(admin),sql.Identifier(user)))
            c.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO {}').format(sql.Identifier(admin),sql.Identifier(user)))
        self.stdout.write('Runtime role provisioned without superuser/CREATEDB/CREATEROLE. Password omitted.')
