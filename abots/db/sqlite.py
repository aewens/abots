from abots.helpers import eprint

from os import stat, remove
from os.path import dirname, basename, isfile, isdir, join as path_join
from shutil import copyfile
from time import strftime
from operator import itemgetter
from sqlite3 import connect, Error as SQLiteError

class Quill:
    def __init__(self, db_file):
        self.db_file = db_file
        self.path = dirname(self.db_file)
        self.filename = basename(self.db_file)
        self.connection = None
        self.cursor = None
        self.memory = False
        self._load()

    def _load(self):
        try:
            self.connection = connect(db_file)
        except SQLiteError as e:
            eprint(e)
            self.connection = connect(":memory:")
            self.memory = True
        self.cursor = self.connection.cursor()

    def _unload(self):
        self.conn.close()

    # Must be called from `backup`
    def _remove_old_backups(self, backup_dir, backups):
        contents = listdir(backup_dir)
        files = [(f, stat(f).st_mtime) for f in contents if isfile(f)]
        # Sort by mtime
        files.sort(key=itemgetter(1))
        remove_files = files[:-backups]
        for rfile in remove_files:
            remove(rfile)

    def backup(self, backup_dir=None, backups=1):
        if backup_dir is None:
            backup_dir = 
        if not isdir(backup_dir):
            eprint("ERROR: Backup directory does not exist")
            return None
        suffix = strftime("-%Y%m%d-%H%M%S")
        backup_name = f"{self.filename} {suffix}"
        backup_file = path_join(backup_dir, backup_name)
        # Lock database
        self.cursor.execute("begin immediate")
        copyfile(self.db_file, backup_file)
        # Unlock database
        self.connection.rollback()
        self._remove_old_backups(backup_dir, backups)

    def execute(self, executor, commit=True, *args):
        if "?" in executor:
            result = self.cursor.execute(executor, *args)
        else:
            result = self.cursor.execute(executor)
        if commit:
            self.connection.commit()
        return result

    def fetch(self, executor, *args):
        return self.execute(executor, commit=False, *args).fetchall()

    def create_table(self, name, fields):
        _fields = list()
        for field in fields:
            name = field.get("name", None)
            kind = field.get("kind", None)
            attr = field.get("attr", None)
            if None in [name, kind, attr] or type(attr) != list:
                return None
            _fields.append(f"{name} {kind} {" ".join(attr)}")
        field_string = ", ".join(_fields)
        executor = f"CREATE TABLE {self.name}({field_string})"
        self.execute(executor)
        return True

    def insert_values(self, table, values):
        if type(values) != list:
            values = [values]
        values_string = ", ".join(values)
        executor = f"INSERT INTO {table} VALUES({values_string})"
        self.execute(executor)
        return True

    def select(self, table, values, where=None):
        if type(values) != list:
            values = [values]
        values_string = ", ".join(values)
        executor = f"SELECT {values_string} FROM"
        if where:
            executor = f"{executor} WHERE {}"