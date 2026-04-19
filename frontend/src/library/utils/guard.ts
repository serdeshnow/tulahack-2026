export const guard = {
  null: <T>(t: T | null): t is null => t === null,

  obj: (t: unknown): t is Record<string, unknown> => typeof t === 'object' && !guard.null(t) && !guard.arr(t),

  arr: <T, U>(t: Array<T> | U): t is Array<T> => Array.isArray(t),

  map: <K, V, U>(t: Map<K, V> | U): t is Map<K, V> => t instanceof Map,

  set: <T, U>(t: Set<T> | U): t is Set<T> => t instanceof Set,

  date: <U>(t: Date | U): t is Date => t instanceof Date,

  undefined: <T>(t: T | undefined): t is undefined => typeof t === 'undefined',

  bool: <U>(t: boolean | U): t is boolean => typeof t === 'boolean',

  num: <U>(t: number | U): t is number => typeof t === 'number' && !Number.isNaN(t),

  str: <U>(t: string | U): t is string => typeof t === 'string',

  bigInt: <U>(t: bigint | U): t is bigint => typeof t === 'bigint',

  sym: <U>(t: symbol | U): t is symbol => typeof t === 'symbol',

  // eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
  fn: <T extends Function, U>(t: T | U): t is T => typeof t === 'function',

  prom: <T extends Promise<unknown>, U>(t: T | U): t is T => t instanceof Promise || (guard.obj(t) && 'then' in t),

  prim: (t: unknown): t is string | number | boolean | symbol | null | undefined | bigint =>
    guard.null(t) ||
    guard.str(t) ||
    guard.num(t) ||
    guard.bool(t) ||
    guard.sym(t) ||
    guard.undefined(t) ||
    guard.bigInt(t)
}
