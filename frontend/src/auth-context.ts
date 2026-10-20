import { createContext, useContext } from 'react'
import type { User } from './api'

interface AuthCtx { user: User | null; can: (perm: string) => boolean; logout: () => void }
export const Ctx = createContext<AuthCtx>({ user: null, can: () => false, logout: () => {} })
export const useAuth = () => useContext(Ctx)
