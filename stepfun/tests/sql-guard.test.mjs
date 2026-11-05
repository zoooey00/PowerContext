import { test } from "node:test";
import assert from "node:assert/strict";
import { Collection } from "seekdb";
import { guardCollection } from "../sql-guard.mjs";
function check(sql) {
  const c = guardCollection({
    validateDynamicSql: Collection.prototype.validateDynamicSql,
  });
  c.validateDynamicSql(sql);
}
test("ordinary query words and semicolons in literals are accepted", () => {
  check(
    "SELECT * FROM documents WHERE text='How to call and update a model; safely?' ",
  );
  check("SELECT * FROM documents WHERE text='user\\'s call' ");
  check("SELECT * FROM documents WHERE text='user''s update' ");
});
test("SQL structure defenses are retained", () => {
  for (const sql of [
    "DELETE FROM documents",
    "SELECT 1; DROP TABLE documents",
    "SELECT 1 INTO OUTFILE 'x'",
    "SELECT 1 /*! DROP TABLE x */",
    "SELECT 'unterminated",
  ])
    assert.throws(() => check(sql));
});
