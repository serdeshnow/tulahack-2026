import { useMemo, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'

import { env, getAccessToken, routes } from '@/application/core'
import { AuthService } from '@/adapter/tulahack/auth'
import { Button } from '@/library/ui/button'
import { Card } from '@/library/ui/card'
import { Input } from '@/library/ui/input'
import { Label } from '@/library/ui/label'

const authService = new AuthService()

export function AuthPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const accessToken = getAccessToken()

  const redirectPath = useMemo(() => {
    const state = location.state as { from?: { pathname?: string } } | null
    return state?.from?.pathname ?? routes.main.root
  }, [location.state])

  const loginMutation = useMutation({
    mutationFn: () => authService.login({ username, password }),
    onSuccess: () => {
      toast.success('Сессия обновлена')
      navigate(redirectPath, { replace: true })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Не удалось войти')
    }
  })

  if (accessToken || env.VITE_ALLOW_GUEST_ACCESS) {
    return <Navigate to={redirectPath} replace />
  }

  return (
    <main className='flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(100,104,240,0.18),_transparent_40%),linear-gradient(135deg,#f8f8f8_0%,#eef2ff_45%,#f5f7fb_100%)] px-6'>
      <Card className='w-full max-w-md border-white/70 bg-white/90 py-0 backdrop-blur'>
        <Card.Header className='border-b py-6'>
          <div className='mb-3 flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary'>
            <ShieldCheck />
          </div>
          <Card.Title className='text-2xl'>Voice Data Redaction</Card.Title>
          <Card.Description>Войдите, чтобы управлять загрузкой, проверкой и экспортом анонимизированных записей.</Card.Description>
        </Card.Header>
        <Card.Content className='space-y-5 py-6'>
          <div className='space-y-2'>
            <Label htmlFor='username'>Логин</Label>
            <Input id='username' value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='password'>Пароль</Label>
            <Input
              id='password'
              type='password'
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
        </Card.Content>
        <Card.Footer className='border-t py-4'>
          <Button
            className='w-full'
            disabled={!username || !password || loginMutation.isPending}
            onClick={() => loginMutation.mutate()}
          >
            {loginMutation.isPending ? 'Входим...' : 'Войти'}
          </Button>
        </Card.Footer>
      </Card>
    </main>
  )
}
