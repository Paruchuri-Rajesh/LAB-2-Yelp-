/**
 * Backwards-compatible `useAuth` hook.
 *
 * Lab 1 used React Context for auth; Lab 2 moved auth state into Redux
 * (see `src/store/slices/authSlice.js`). This module keeps the old
 * `useAuth()` surface so existing pages (`LoginPage`, `ProfilePage`, …)
 * continue to work unchanged while actually reading from the Redux store.
 */
import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  loginUser, signupUser, logoutUser, fetchCurrentUser, setUser,
  selectCurrentUser, selectAuthToken,
} from '../store/slices/authSlice'

export function AuthProvider({ children }) {
  // No-op provider kept so <AuthProvider> in legacy code remains valid.
  return children
}

export function useAuth() {
  const dispatch = useDispatch()
  const user = useSelector(selectCurrentUser)
  const token = useSelector(selectAuthToken)

  useEffect(() => {
    if (token && !user) {
      dispatch(fetchCurrentUser())
    }
  }, [dispatch, token, user])

  return {
    user,
    token,
    login: (credentials) => dispatch(loginUser(credentials)).unwrap(),
    signup: (payload) => dispatch(signupUser(payload)).unwrap(),
    logout: () => dispatch(logoutUser()),
    refreshUser: (updated) => dispatch(setUser(updated)),
  }
}
