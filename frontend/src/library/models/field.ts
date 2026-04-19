import { DataModel, model, modelAction, prop, ModelCreationData } from 'mobx-keystone'
import { Constraint, checkConstraints } from '@utils/constraints'
import { collect } from '../utils'

const FKey = 'fields'

type FieldProps<T extends string = string> = ModelCreationData<typeof Field> & {
  id: T
}

type Schema<T extends string = string> = {
  [key: string]: {
    [key: string]: unknown
    [FKey]?: FieldProps<T>[]
  }
}

@model('Field')
class Field extends DataModel({
  id: prop(''),
  type: prop('text'),
  value: prop<string>(''),
  label: prop(''),
  placeholder: prop(''),
  constraints: prop<Constraint[]>(() => []),
  touched: prop(false),
  validation: prop<'submit' | 'blur'>('blur'),
  error: prop<string | null>(null)
}) {
  @modelAction
  onChange = (value: string) => {
    this.value = value
  }

  @modelAction
  onBlur = () => {
    if (this.validation === 'blur') this.validate()
  }

  @modelAction
  validate = () => {
    this.touched = true
    this.error = checkConstraints(this.value, this.constraints)
  }

  static collect = <T extends string>(schema: Schema<T>, key = FKey) => {
    return collect<FieldProps<T>>(schema, key).reduce((acc, field) => ({ ...acc, [field.id]: new Field(field) }), {})
  }
}

export type { FieldProps }
export default Field
