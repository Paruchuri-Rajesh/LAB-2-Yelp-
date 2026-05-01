import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { login as apiLogin, signup as apiSignup } from '../../api/auth'
import client from '../../api/client'

const token = () => localStorage.getItem('access_token')
const storedUser = () => {
  try {
    const raw = localStorage.getItem('user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

const persist = (accessToken, user) => {
  if (accessToken) localStorage.setItem('access_token', accessToken)
  if (user) localStorage.setItem('user', JSON.stringify(user))
}
const clearPersisted = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
}

export const loginUser = createAsyncThunk('auth/login', async (credentials, { rejectWithValue }) => {
  try {
    const { data } = await apiLogin(credentials)
    persist(data.access_token, data.user)
    return data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Login failed')
  }
})

export const signupUser = createAsyncThunk('auth/signup', async (payload, { rejectWithValue }) => {
  try {
    const { data } = await apiSignup(payload)
    persist(data.access_token, data.user)
    return data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Signup failed')
  }
})

export const fetchCurrentUser = createAsyncThunk('auth/fetchMe', async (_, { rejectWithValue }) => {
  try {
    const { data } = await client.get('/users/me')
    persist(null, data)
    return data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Not authenticated')
  }
})

export const logoutUser = createAsyncThunk('auth/logout', async () => {
  try { await client.post('/auth/logout') } catch { /* best effort */ }
  clearPersisted()
})

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: storedUser(),
    token: token(),
    status: 'idle',
    error: null,
  },
  reducers: {
    setUser(state, action) {
      state.user = action.payload
      persist(null, action.payload)
    },
  },
  extraReducers: (builder) => {
    const handleAuth = (state, { payload }) => {
      state.user = payload.user
      state.token = payload.access_token
      state.status = 'succeeded'
      state.error = null
    }
    builder
      .addCase(loginUser.pending, (s) => { s.status = 'loading'; s.error = null })
      .addCase(loginUser.fulfilled, handleAuth)
      .addCase(loginUser.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload })
      .addCase(signupUser.pending, (s) => { s.status = 'loading'; s.error = null })
      .addCase(signupUser.fulfilled, handleAuth)
      .addCase(signupUser.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload })
      .addCase(fetchCurrentUser.fulfilled, (s, a) => { s.user = a.payload })
      .addCase(fetchCurrentUser.rejected, (s) => {
        s.user = null; s.token = null; clearPersisted()
      })
      .addCase(logoutUser.fulfilled, (s) => {
        s.user = null; s.token = null; s.status = 'idle'; s.error = null
      })
  },
})

export const { setUser } = authSlice.actions

export const selectCurrentUser = (state) => state.auth.user
export const selectAuthToken = (state) => state.auth.token
export const selectAuthStatus = (state) => state.auth.status
export const selectAuthError = (state) => state.auth.error
export const selectIsAuthenticated = (state) => Boolean(state.auth.token && state.auth.user)

export default authSlice.reducer
