export type Nullable<T> = {
  [K in keyof T]: T[K] | null
}

export type Mutable<T> = { -readonly [P in keyof T]: T[P] }
export const asMutable = <T>(value: T): Mutable<T> => value as Mutable<T>

export type DeepMap<T, V = boolean> =
  | V
  | (T extends object
      ? (keyof T extends string ? Array<keyof T & string> : never) | { [K in keyof T]?: DeepMap<T[K], V> }
      : never)

// export type Values<T, V = never> =
//   | ([V] extends [never] ? T : V)
//   | (T extends object
//       ? (keyof T extends string ? Array<keyof T & string> : never) | { [K in keyof T]?: Values<T[K], V> }
//       : never);

export type Values<T, V = never, Keys extends boolean = false> =
  | ([V] extends [never] ? T : T | V)
  | (T extends object
      ?
          | (Keys extends true ? (keyof T extends string ? Array<keyof T & string> : never) : never)
          | { [K in keyof T]?: Values<T[K], V, Keys> }
      : never)

export type Strings<T> = {
  [K in keyof T]: T[K] extends string
    ? T[K]
    : T[K] extends number
      ? `${T[K]}`
      : T[K] extends Array<infer U>
        ? Array<U extends number ? `${U}` : U>
        : never
}

export type ExtractParams<Key extends string> = Key extends `${string}:${infer Param}/${infer Rest}`
  ? { [k in Param | keyof ExtractParams<`/${Rest}`>]: string }
  : Key extends `${string}:${infer Param}`
    ? { [k in Param]: string }
    : Record<string, never>
