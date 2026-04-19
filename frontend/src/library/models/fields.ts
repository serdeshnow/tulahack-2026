import { computed, observable } from 'mobx'
import { model, modelAction, Model } from 'mobx-keystone'
import { Constraint, checkConstraints, modelProps, guard, collect } from '@utils'

const FKey = 'fields'

const data = {
  attr: {} as Record<string, Record<string, unknown>>,
  values: {} as Record<string, string>,
  errors: {} as Record<string, string | null | undefined>,
  touched: {} as Record<string, boolean>,
  constraints: {} as Record<string, Constraint[]>,
  validation: 'submit' as Validation
}

type Data = typeof data

export type Field<Ctx = unknown> = {
  [key: string]: unknown
  id: string
  constraints?: Constraint[]
  value?: string
  label?: string
  labelFn?: (context: Ctx) => string
  touched?: boolean
  type?: string
  placeholder?: string
  maxLength?: number
}

type Node<Ctx> = Schema<Ctx> | Field<Ctx>[] | string | number | boolean | null | undefined
type Schema<Ctx> = {
  [K in string]: K extends typeof FKey ? Field<Ctx>[] : Node<Ctx>
}

type Validation = 'blur' | 'submit'

@model('Fields')
export class Fields<Ctx = unknown> extends Model(modelProps(data)) {
  _fields: Record<string, Field<Ctx>> = {}

  @observable
  context: Ctx | undefined = undefined

  @computed
  get labels() {
    return Object.fromEntries(
      Object.keys(this.values).map((id) => {
        const label = this._fields[id]?.labelFn || this.attr[id]?.label
        return [id, guard.fn(label) ? label(this.context) : label || '']
      })
    )
  }

  @computed
  get valid() {
    return !Object.values(this.errors).some((err) => err)
  }

  @modelAction
  setContext = (context: Ctx) => {
    this.context = context
  }

  @modelAction
  validate = (fields?: Field<Ctx>[] | boolean) => {
    if (!fields) return true

    let valid = true

    const ids = guard.arr(fields) ? fields.map((f) => f.id) : Object.keys(this.values)

    for (const id of ids) {
      this.touched[id] = true
      valid = valid && !this.errors[id]
    }

    return valid
  }

  @modelAction
  onChange = (id: string, value: string) => {
    if (this.validation !== 'blur') this.touched[id] = false

    this.values[id] = value
    this.errors[id] = checkConstraints(value, this.constraints[id])
  }

  @modelAction
  onBlur = (id: string) => {
    if (this.validation === 'blur') this.touched[id] = true
  }

  @modelAction
  reset = () => {
    Object.keys(this.values).forEach((id) => {
      this.values[id] = ''
      this.errors[id] = null
      this.touched[id] = false
    })
  }

  @modelAction
  static create = <Ctx = unknown>(schema: Schema<Ctx>, props: Partial<Data> = {}) => {
    const fields = collect<Field<Ctx>>(schema, FKey)

    const snapshot = { ...data, ...props }

    fields.forEach(({ id, ...field }) => {
      snapshot.attr[id] = field
      snapshot.values[id] = field.value || ''
      snapshot.touched[id] = field.touched || false
      snapshot.constraints[id] = field.constraints || []
      snapshot.errors[id] = checkConstraints(field.value || '', field.constraints)
    })

    const model = new Fields<Ctx>(snapshot)

    model._fields = Object.fromEntries(fields.map((field) => [field.id, field]))

    return model
  }
}

export default Fields
