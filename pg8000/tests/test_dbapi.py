import unittest
import os
import time
import pg8000
import datetime
from contextlib import closing
from .connection_settings import db_connect

dbapi = pg8000.DBAPI
db2 = dbapi.connect(**db_connect)


# DBAPI compatible interface tests
class Tests(unittest.TestCase):
    def setUp(self):
        os.environ['TZ'] = "UTC"
        time.tzset()
        with closing(db2.cursor()) as c:
            try:
                c.execute("DROP TABLE t1")
            except pg8000.DatabaseError as e:
                # the only acceptable error is:
                self.assert_(
                    e.args[1] == b'42P01',  # table does not exist
                    "incorrect error for drop table")
                db2.rollback()
            c.execute(
                "CREATE TEMPORARY TABLE t1 "
                "(f1 int primary key, f2 int not null, f3 varchar(50) null)")
            c.execute(
                "INSERT INTO t1 (f1, f2, f3) VALUES (%s, %s, %s)",
                (1, 1, None))
            c.execute(
                "INSERT INTO t1 (f1, f2, f3) VALUES (%s, %s, %s)",
                (2, 10, None))
            c.execute(
                "INSERT INTO t1 (f1, f2, f3) VALUES (%s, %s, %s)",
                (3, 100, None))
            c.execute(
                "INSERT INTO t1 (f1, f2, f3) VALUES (%s, %s, %s)",
                (4, 1000, None))
            c.execute(
                "INSERT INTO t1 (f1, f2, f3) VALUES (%s, %s, %s)",
                (5, 10000, None))
            db2.commit()

    def testParallelQueries(self):
        with closing(db2.cursor()) as c1, closing(db2.cursor()) as c2:
            c1.execute("SELECT f1, f2, f3 FROM t1")
            while 1:
                row = c1.fetchone()
                if row is None:
                    break
                f1, f2, f3 = row
                c2.execute("SELECT f1, f2, f3 FROM t1 WHERE f1 > %s", (f1,))
                while 1:
                    row = c2.fetchone()
                    if row is None:
                        break
                    f1, f2, f3 = row
        db2.rollback()

    def testQmark(self):
        orig_paramstyle = dbapi.paramstyle
        try:
            dbapi.paramstyle = "qmark"
            with closing(db2.cursor()) as c1:
                c1.execute("SELECT f1, f2, f3 FROM t1 WHERE f1 > ?", (3,))
                while 1:
                    row = c1.fetchone()
                    if row is None:
                        break
                    f1, f2, f3 = row
            db2.rollback()
        finally:
            dbapi.paramstyle = orig_paramstyle

    def testNumeric(self):
        orig_paramstyle = dbapi.paramstyle
        try:
            dbapi.paramstyle = "numeric"
            with closing(db2.cursor()) as c1:
                c1.execute("SELECT f1, f2, f3 FROM t1 WHERE f1 > :1", (3,))
                while 1:
                    row = c1.fetchone()
                    if row is None:
                        break
                    f1, f2, f3 = row
            db2.rollback()
        finally:
            dbapi.paramstyle = orig_paramstyle

    def testNamed(self):
        orig_paramstyle = dbapi.paramstyle
        try:
            dbapi.paramstyle = "named"
            with closing(db2.cursor()) as c1:
                c1.execute(
                    "SELECT f1, f2, f3 FROM t1 WHERE f1 > :f1", {"f1": 3})
                while 1:
                    row = c1.fetchone()
                    if row is None:
                        break
                    f1, f2, f3 = row
            db2.rollback()
        finally:
            dbapi.paramstyle = orig_paramstyle

    def testFormat(self):
        orig_paramstyle = dbapi.paramstyle
        try:
            dbapi.paramstyle = "format"
            with closing(db2.cursor()) as c1:
                c1.execute("SELECT f1, f2, f3 FROM t1 WHERE f1 > %s", (3,))
                while 1:
                    row = c1.fetchone()
                    if row is None:
                        break
                    f1, f2, f3 = row
            db2.commit()
        finally:
            dbapi.paramstyle = orig_paramstyle

    def testPyformat(self):
        orig_paramstyle = dbapi.paramstyle
        try:
            dbapi.paramstyle = "pyformat"
            with closing(db2.cursor()) as c1:
                c1.execute(
                    "SELECT f1, f2, f3 FROM t1 WHERE f1 > %(f1)s", {"f1": 3})
                while 1:
                    row = c1.fetchone()
                    if row is None:
                        break
                    f1, f2, f3 = row
            db2.commit()
        finally:
            dbapi.paramstyle = orig_paramstyle

    def testArraysize(self):
        with closing(db2.cursor()) as c1:
            c1.arraysize = 3
            c1.execute("SELECT * FROM t1")
            retval = c1.fetchmany()
            self.assertEquals(len(retval), c1.arraysize)
        db2.commit()

    def testDate(self):
        val = dbapi.Date(2001, 2, 3)
        self.assertEquals(val, datetime.date(2001, 2, 3))

    def testTime(self):
        val = dbapi.Time(4, 5, 6)
        self.assertEquals(val, datetime.time(4, 5, 6))

    def testTimestamp(self):
        val = dbapi.Timestamp(2001, 2, 3, 4, 5, 6)
        self.assertEquals(val, datetime.datetime(2001, 2, 3, 4, 5, 6))

    def testDateFromTicks(self):
        val = dbapi.DateFromTicks(1173804319)
        self.assertEqual(val, datetime.date(2007, 3, 13))

    def testTimeFromTicks(self):
        val = dbapi.TimeFromTicks(1173804319)
        self.assertEquals(val, datetime.time(16, 45, 19))

    def testTimestampFromTicks(self):
        val = dbapi.TimestampFromTicks(1173804319)
        self.assertEquals(val, datetime.datetime(2007, 3, 13, 16, 45, 19))

    def testBinary(self):
        v = dbapi.Binary(b"\x00\x01\x02\x03\x02\x01\x00")
        self.assertEqual(v, b"\x00\x01\x02\x03\x02\x01\x00")
        self.assertIsInstance(v, dbapi.BINARY)

    def testRowCount(self):
        with closing(db2.cursor()) as c1:
            c1.execute("SELECT * FROM t1")
            self.assertEquals(5, c1.rowcount)

            c1.execute("UPDATE t1 SET f3 = %s WHERE f2 > 101", ("Hello!",))
            self.assertEquals(2, c1.rowcount)

            c1.execute("DELETE FROM t1")
            self.assertEquals(5, c1.rowcount)
        db2.commit()

    def testFetchMany(self):
        with closing(db2.cursor()) as cursor:
            cursor.arraysize = 2
            cursor.execute("SELECT * FROM t1")
            self.assertEquals(2, len(cursor.fetchmany()))
            self.assertEquals(2, len(cursor.fetchmany()))
            self.assertEquals(1, len(cursor.fetchmany()))
            self.assertEquals(0, len(cursor.fetchmany()))
        db2.commit()

    def testIterator(self):
        from warnings import filterwarnings
        filterwarnings("ignore", "DB-API extension cursor.next()")
        filterwarnings("ignore", "DB-API extension cursor.__iter__()")

        with closing(db2.cursor()) as cursor:
            cursor.execute("SELECT * FROM t1 ORDER BY f1")
            f1 = 0
            for row in cursor:
                next_f1 = row[0]
                assert next_f1 > f1
                f1 = next_f1
        db2.commit()

    # Vacuum can't be run inside a transaction, so we need to turn
    # autocommit on.
    def testVacuum(self):
        db2.autocommit = True
        with closing(db2.cursor()) as cursor:
            cursor.execute("vacuum")

if __name__ == "__main__":
    unittest.main()