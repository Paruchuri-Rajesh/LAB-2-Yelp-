import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import {
  getMyFavorites as apiList,
  addFavorite as apiAdd,
  removeFavorite as apiRemove,
} from '../../api/users'

export const fetchFavourites = createAsyncThunk('favourites/fetch', async (_, { rejectWithValue }) => {
  try {
    const { data } = await apiList()
    return data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Failed to load favourites')
  }
})

export const addFavourite = createAsyncThunk('favourites/add', async (restaurantId, { rejectWithValue }) => {
  try {
    await apiAdd(restaurantId)
    return restaurantId
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Failed to add favourite')
  }
})

export const removeFavourite = createAsyncThunk('favourites/remove', async (restaurantId, { rejectWithValue }) => {
  try {
    await apiRemove(restaurantId)
    return restaurantId
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Failed to remove favourite')
  }
})

const favouritesSlice = createSlice({
  name: 'favourites',
  initialState: {
    ids: [],
    items: [],
    status: 'idle',
    error: null,
  },
  reducers: {
    clearFavourites(state) { state.ids = []; state.items = []; state.status = 'idle' },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchFavourites.pending, (s) => { s.status = 'loading'; s.error = null })
      .addCase(fetchFavourites.fulfilled, (s, a) => {
        s.status = 'succeeded'
        s.items = a.payload.items || []
        s.ids = (a.payload.items || []).map((r) => r.id)
      })
      .addCase(fetchFavourites.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload })
      .addCase(addFavourite.fulfilled, (s, a) => {
        if (!s.ids.includes(a.payload)) s.ids.push(a.payload)
      })
      .addCase(removeFavourite.fulfilled, (s, a) => {
        s.ids = s.ids.filter((id) => id !== a.payload)
        s.items = s.items.filter((r) => r.id !== a.payload)
      })
  },
})

export const { clearFavourites } = favouritesSlice.actions

export const selectFavouriteIds = (state) => state.favourites.ids
export const selectFavourites = (state) => state.favourites.items
export const selectFavouritesStatus = (state) => state.favourites.status
export const selectIsFavourited = (restaurantId) => (state) =>
  state.favourites.ids.includes(restaurantId)

export default favouritesSlice.reducer
