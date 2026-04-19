import { requests } from '../setup'
import { schema } from './schema'

const api = requests(schema)

class ApiDocsService {
  read() {
    return api.read()
  }
}

export const apiDocsService = new ApiDocsService()
