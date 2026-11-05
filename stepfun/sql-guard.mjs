// seekdb 1.4.0 scans keywords inside SQL string literals, rejecting ordinary
// questions containing words such as "call" or "update". Preserve its validator
// and apply it to SQL structure with literals/comments masked. Execute original SQL.
export function sqlStructure(sql) {
  let result = "",
    i = 0;
  while (i < sql.length) {
    const c = sql[i];
    if (c === "'" || c === '"') {
      const quote = c;
      i++;
      let closed = false;
      while (i < sql.length) {
        if (sql[i] === "\\") {
          i += 2;
          continue;
        }
        if (sql[i] === quote) {
          if (sql[i + 1] === quote) {
            i += 2;
            continue;
          }
          i++;
          closed = true;
          break;
        }
        i++;
      }
      if (!closed) throw new Error("Unterminated SQL literal");
      result += "'literal'";
      continue;
    }
    if (sql.slice(i, i + 2) === "/*") {
      if (sql[i + 2] === "!")
        throw new Error("Executable SQL comment rejected");
      const end = sql.indexOf("*/", i + 2);
      if (end < 0) throw new Error("Unterminated SQL comment");
      i = end + 2;
      result += " ";
      continue;
    }
    if (c === "#" || sql.slice(i, i + 2) === "--") {
      const end = sql.indexOf("\n", i);
      i = end < 0 ? sql.length : end;
      result += " ";
      continue;
    }
    result += c;
    i++;
  }
  return result;
}
export function guardCollection(c) {
  if (typeof c.validateDynamicSql !== "function")
    throw new Error("Unsupported seekdb SDK SQL validator");
  const validate = c.validateDynamicSql.bind(c);
  c.validateDynamicSql = (sql) => validate(sqlStructure(sql));
  return c;
}
