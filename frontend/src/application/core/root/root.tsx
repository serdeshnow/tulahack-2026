import { useEffect } from 'react'
import { observer } from 'mobx-react-lite'

import { Providers } from '@/application/core/providers'
import store from './store'

import { Loader } from './internal'

const Root = observer(() => {
  useEffect(() => {
    void store.mount()

    return () => {
      void store.unmount()
    }
  }, [])

  if (!store.ready) return <Loader />

  return <Providers />
})

export { Root }

