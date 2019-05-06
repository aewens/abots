from abots.helpers import eprint

from os import stat, remove
from os.path import dirname, basename, isfile, isdir, join as path_join
from shutil import copyfile
from time import strftime
from operator import itemgetter
from contextlib import closing, contextmanager
from threading import Lock
from sqlite3 import (connect, register_converter, PARSE_DECLTYPES, 
    Error as SQLiteError)

register_converter("BOOLEAN", lambda value: bool(int(value)))

class SQLite:
    def __init__(self, db_file, lock=Lock()):
        self.db_file = db_file
        self.path = dirname(self.db_file)
        self.filename = basename(self.db_file)
        self.connection = None
        self.cursor = None
        self.memory = False
        self.lock = lock
        self._load()

    def _load(self):
        settings = dict()
        settings["check_same_thread"] = False
        settings["isolation_level"] = "DEFERRED"
        settings["detect_types"] = PARSE_DECLTYPES
        try:
            self.connection = connect(self.db_file, **settings)
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA foreign_keys = ON")
        except SQLiteError as e:
            eprint(e)
            self.connection = connect(":memory:")
            self.memory = True
        # self.cursor = self.connection.cursor()

    def _unload(self):
        self.connection.close()

    # Must be called from `backup`
    def _remove_old_backups(self, backup_dir, backups):
        contents = listdir(backup_dir)
        files = [(f, stat(f).st_mtime) for f in contents if isfile(f)]
        # Sort by mtime
        files.sort(key=itemgetter(1))
        remove_files = files[:-backups]
        for rfile in remove_files:
            remove(rfile)

    def _convert(self, values):
        convert = lambda value: value if not None else "NULL"
        return (convert(value) for value in values)

    def stop(self):
        self._unload()

    def backup(self, backup_dir=None, backups=1):
        if backup_dir is None:
            backup_dir = self.path
        if not isdir(backup_dir):
            eprint("ERROR: Backup directory does not exist")
            return None
        suffix = strftime("-%Y%m%d-%H%M%S")
        backup_name = f"{self.filename} {suffix}"
        backup_file = path_join(backup_dir, backup_name)
        # Lock database
        with closing(self.connection.cursor()) as cursor:
            cursor.execute("begin immediate")
            copyfile(self.db_file, backup_file)
        # Unlock database
        self.conenction.rollback()
        self._remove_old_backups(backup_dir, backups)

    def execute(self, executor, values=tuple(), fetch=False):
        with closing(self.connection.cursor()) as cursor:
            if "?" in executor:
                result = cursor.execute(executor, values)
            else:
                result = cursor.execute(executor)
            if not fetch:
                return True
            return cursor.fetchall()

    def fetch(self, executor, values=tuple()):
        return self.execute(executor, values, fetch=True)

    def create_table(self, name, fields):
        fields_string = ",".join(fields)
        executor = f"CREATE TABLE {name} ({fields_string})"
        return self.execute(executor)

    def insert(self, table, insertion):
        assert isinstance(insertion, dict), "Expected dict"
        keys = ",".join(insertion.keys())
        places = ",".join(["?"] * len(insertion))
        values = tuple(self._convert(insertion.values()))
        executor = f"INSERT INTO {table} ({keys}) VALUES({places})"
        return self.execute(executor, values)

    def update(self, table, modification, where):
        assert isinstance(modification, dict), "Expected dict"
        assert isinstance(where, tuple), "Expected tuple"
        assert len(where) == 2, "Expected length of '2'"
        assert isinstance(where[0], str), "Expected str"
        assert isinstance(where[1], tuple), "Expected tuple"
        keys = ",".join(f"{key} = ?" for key in modification.keys())
        mod_values = tuple(self._convert(modification.values()))
        where_query = where[0]
        where_values = where[1]
        values = mod_values + where_values
        executor = f"UPDATE {table} SET {keys} WHERE {where_query}"
        return self.execute(executor, values)

    def lookup(self, table, search, where=None):
        if type(search) != list:
            search = [search]
        keys = ",".join(search)
        executor = f"SELECT {keys} FROM {table}"
        if where:
            assert isinstance(where, tuple), "Expected tuple"
            assert len(where) == 2, "Expected length of '2'"
            assert isinstance(where[0], str), "Expected str"
            assert isinstance(where[1], tuple), "Expected tuple"
            where_query = where[0]
            where_values = where[1]
            executor = f"{executor} WHERE {where_query}"
            return self.fetch(executor, where_values)
        return self.fetch(executor)

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield
                self.connection.commit()
            except:
                self.connection.rollback()
                raise