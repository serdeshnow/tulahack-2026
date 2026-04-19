import { computed } from 'mobx'
import { Model, model, ModelData, prop } from 'mobx-keystone'

@model('User')
class UserModel extends Model({
  name: prop(''),
  avatar: prop(''),
  email: prop(''),
  maskedEmail: prop('')
}) {
  @computed
  get letter() {
    return this.name.charAt(0)
  }
}

export type User = ModelData<UserModel>

export default UserModel
