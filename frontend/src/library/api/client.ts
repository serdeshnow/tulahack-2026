import axios, { AxiosError } from 'axios';
import type { IError, Config, ILogger, Instance } from './types';

export class Client {
  instance!: Instance;

  constructor(config: Config, logger?: ILogger, createError?: (error: AxiosError) => IError) {
    this.instance = axios.create({ baseURL: config.base, withCredentials: config.withCredentials ?? false });

    this.instance.interceptors.request.use((request) => {
      const token = typeof config.token === 'function' ? config.token() : config.token;
      const xToken = typeof config.xToken === 'function' ? config.xToken() : config.xToken;

      request.headers = request.headers || {};

      if (token) {
        request.headers['Authorization'] = `Bearer ${token}`;
      }

      if (xToken) {
        request.headers['X-Token'] = xToken;
      }

      logger?.log('request', request);
      return request;
    }, Promise.reject);

    this.instance.interceptors.response.use(
      (axiosResponse) => {
        logger?.log('response', axiosResponse);
        return axiosResponse.data || axiosResponse;
      },

      (axiosError) => {
        logger?.log('error', axiosError);

        const error = createError?.(axiosError) ?? axiosError;

        return Promise.reject(error);
      }
    );
  }
}
