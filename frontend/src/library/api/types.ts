import { type AxiosInstance, AxiosError } from 'axios'

export type Instance = AxiosInstance

export type Config = {
  base: string
  token?: string | (() => string | null | undefined)
  xToken?: string | (() => string | null | undefined)
  withCredentials?: boolean
  dev?: boolean
  mock?: boolean
}

type IsNever<T> = [T] extends [never] ? true : false
type NonNeverKeys<Path, Query, Body> = {
  path: IsNever<Path> extends true ? never : 'path'
  query: IsNever<Query> extends true ? never : 'query'
  body: IsNever<Body> extends true ? never : 'body'
}

export type RequestParts<Path = never, Query = never, Body = never> = {
  path: Path
  query: Query
  body: Body
}

type PresentRequestKeys<Path, Query, Body> = NonNeverKeys<Path, Query, Body>[keyof NonNeverKeys<Path, Query, Body>]
type PresentRequestShape<Path, Query, Body> = Pick<RequestParts<Path, Query, Body>, PresentRequestKeys<Path, Query, Body>>

export type RequestInput<Path = never, Query = never, Body = never> =
  keyof PresentRequestShape<Path, Query, Body> extends never
    ? void
    : keyof PresentRequestShape<Path, Query, Body> extends 'body'
      ? Body
      : keyof PresentRequestShape<Path, Query, Body> extends 'query'
        ? Query
        : keyof PresentRequestShape<Path, Query, Body> extends 'path'
          ? Path
          : PresentRequestShape<Path, Query, Body>

export type EndpointResponse<Raw = unknown, Res = Raw> = Res | ((raw: Raw) => Res)

export type EndpointSpec<Path = never, Query = never, Body = never, Raw = unknown, Res = Raw> = {
  url: string
  request: RequestInput<Path, Query, Body>
  response: EndpointResponse<Raw, Res>
  formData?: boolean
  responseType?: 'blob' | 'text' | 'json'
  method?: 'get' | 'post' | 'put' | 'delete' | 'patch'
  errors?: readonly string[]
}

export type ApiModule<S extends Schema = Schema, E extends Record<string, string> = Record<string, string>> = {
  schema: S
  errors?: E
  mocks: readonly string[]
}

export const defineApiModule = <S extends Schema, E extends Record<string, string> = Record<string, string>>(
  module: ApiModule<S, E>
): ApiModule<S, E> => module

export type Schema = Record<
  string,
  {
    url: string
    request: unknown
    response: unknown
    formData?: boolean
    responseType?: 'blob' | 'text' | 'json'
    method?: 'get' | 'post' | 'put' | 'delete' | 'patch'
    errors?: readonly string[]
  }
>

type ResolveResponse<T> = T extends (...args: never[]) => infer R ? R : T
type ResolveRawResponse<T> = T extends (raw: infer Raw) => unknown ? Raw : T
type MapperArgs<T> = [T] extends [void] ? [] : [data: T]

export type SchemaMapper<S extends Schema, asPromise extends boolean = true> = {
  [K in keyof S]: (
    ...args: MapperArgs<S[K]['request']>
  ) => asPromise extends true ? Promise<ResolveResponse<S[K]['response']>> : ResolveResponse<S[K]['response']>
}

export type SchemaRawMapper<S extends Schema, asPromise extends boolean = true> = {
  [K in keyof S]: (
    ...args: MapperArgs<S[K]['request']>
  ) => asPromise extends true ? Promise<ResolveRawResponse<S[K]['response']>> : ResolveRawResponse<S[K]['response']>
}

export type LogType = {
  request: boolean
  response: boolean
  error: boolean
}

export interface ILogger {
  log: (type: keyof LogType, payload: unknown) => void
}

export interface IErrors {
  create: (error: AxiosError) => { status?: number }
}

export interface IError {
  message: string | undefined
  data: Record<string, unknown> | undefined
  status: number | undefined
  _error: AxiosError
}
