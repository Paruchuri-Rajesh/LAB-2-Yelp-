import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import * as ownerApi from '../../api/owner'

const reject = (rejectWithValue) => (err) =>
  rejectWithValue(err.response?.data?.detail || err.message || 'Owner request failed')

export const claimRestaurant = createAsyncThunk(
  'owner/claimRestaurant',
  async (restaurantId, { rejectWithValue }) => {
    try { const res = await ownerApi.claimRestaurant(restaurantId); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const fetchOwnerDashboard = createAsyncThunk(
  'owner/fetchOwnerDashboard',
  async (_, { rejectWithValue }) => {
    try { const res = await ownerApi.getOwnerDashboard(); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const fetchOwnedRestaurants = createAsyncThunk(
  'owner/fetchOwnedRestaurants',
  async (_, { rejectWithValue }) => {
    try { const res = await ownerApi.getOwnedRestaurants(); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const fetchOwnerRestaurantDashboard = createAsyncThunk(
  'owner/fetchOwnerRestaurantDashboard',
  async (restaurantId, { rejectWithValue }) => {
    try { const res = await ownerApi.getOwnerRestaurantDashboard(restaurantId); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const createOwnedRestaurant = createAsyncThunk(
  'owner/createOwnedRestaurant',
  async (formData, { rejectWithValue }) => {
    try { const res = await ownerApi.createOwnedRestaurant(formData); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const updateOwnedRestaurant = createAsyncThunk(
  'owner/updateOwnedRestaurant',
  async ({ id, data }, { rejectWithValue }) => {
    try { const res = await ownerApi.updateOwnedRestaurant(id, data); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const uploadOwnedRestaurantPhotos = createAsyncThunk(
  'owner/uploadOwnedRestaurantPhotos',
  async ({ id, formData }, { rejectWithValue }) => {
    try { const res = await ownerApi.uploadOwnedRestaurantPhotos(id, formData); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const deleteOwnedRestaurantPhoto = createAsyncThunk(
  'owner/deleteOwnedRestaurantPhoto',
  async ({ id, photoId }, { rejectWithValue }) => {
    try { const res = await ownerApi.deleteOwnedRestaurantPhoto(id, photoId); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

export const updateOwnedRestaurantHours = createAsyncThunk(
  'owner/updateOwnedRestaurantHours',
  async ({ id, data }, { rejectWithValue }) => {
    try { const res = await ownerApi.updateOwnedRestaurantHours(id, data); return res.data }
    catch (err) { return reject(rejectWithValue)(err) }
  },
)

const ownerSlice = createSlice({
  name: 'owner',
  initialState: {
    dashboard: null,
    currentRestaurant: null,
    restaurants: [],
    lastClaim: null,
    status: 'idle',
    error: null,
  },
  reducers: {
    clearOwnerError(state) { state.error = null },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchOwnerDashboard.fulfilled, (state, action) => {
        state.dashboard = action.payload
      })
      .addCase(fetchOwnedRestaurants.fulfilled, (state, action) => {
        state.restaurants = action.payload
      })
      .addCase(fetchOwnerRestaurantDashboard.fulfilled, (state, action) => {
        state.currentRestaurant = action.payload
      })
      .addCase(claimRestaurant.fulfilled, (state, action) => {
        state.lastClaim = action.payload
      })
      .addCase(createOwnedRestaurant.fulfilled, (state, action) => {
        state.restaurants = [action.payload, ...state.restaurants]
      })
      .addCase(updateOwnedRestaurant.fulfilled, (state, action) => {
        if (state.currentRestaurant?.restaurant) {
          state.currentRestaurant.restaurant = action.payload
        }
      })
      .addMatcher(
        (action) => action.type.startsWith('owner/') && action.type.endsWith('/pending'),
        (state) => { state.status = 'loading'; state.error = null },
      )
      .addMatcher(
        (action) => action.type.startsWith('owner/') && action.type.endsWith('/fulfilled'),
        (state) => { state.status = 'succeeded' },
      )
      .addMatcher(
        (action) => action.type.startsWith('owner/') && action.type.endsWith('/rejected'),
        (state, action) => { state.status = 'failed'; state.error = action.payload },
      )
  },
})

export const { clearOwnerError } = ownerSlice.actions
export default ownerSlice.reducer
