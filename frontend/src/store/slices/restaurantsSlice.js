import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import {
  searchRestaurants as apiSearch,
  getRestaurant as apiGet,
} from '../../api/restaurants'

export const searchRestaurants = createAsyncThunk('restaurants/search', async (params, { rejectWithValue }) => {
  try {
    const { data } = await apiSearch(params || {})
    return data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Search failed')
  }
})

export const fetchRestaurant = createAsyncThunk('restaurants/get', async (id, { rejectWithValue }) => {
  try {
    const { data } = await apiGet(id)
    return data
  } catch (err) {
    return rejectWithValue(err.response?.data?.detail || 'Restaurant not found')
  }
})

const restaurantsSlice = createSlice({
  name: 'restaurants',
  initialState: {
    list: [],
    total: 0,
    page: 1,
    pageSize: 20,
    pages: 0,
    lastQuery: null,
    listStatus: 'idle',
    listError: null,
    byId: {},
    detailStatus: 'idle',
    detailError: null,
  },
  reducers: {
    clearRestaurants(state) {
      state.list = []
      state.total = 0
      state.pages = 0
      state.lastQuery = null
      state.listStatus = 'idle'
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(searchRestaurants.pending, (s, a) => {
        s.listStatus = 'loading'; s.listError = null; s.lastQuery = a.meta.arg
      })
      .addCase(searchRestaurants.fulfilled, (s, a) => {
        s.list = a.payload.items || []
        s.total = a.payload.total || 0
        s.page = a.payload.page || 1
        s.pageSize = a.payload.page_size || 20
        s.pages = a.payload.pages || 0
        s.listStatus = 'succeeded'
      })
      .addCase(searchRestaurants.rejected, (s, a) => {
        s.listStatus = 'failed'; s.listError = a.payload
      })
      .addCase(fetchRestaurant.pending, (s) => { s.detailStatus = 'loading'; s.detailError = null })
      .addCase(fetchRestaurant.fulfilled, (s, a) => {
        s.detailStatus = 'succeeded'
        if (a.payload?.id) s.byId[a.payload.id] = a.payload
      })
      .addCase(fetchRestaurant.rejected, (s, a) => {
        s.detailStatus = 'failed'; s.detailError = a.payload
      })
  },
})

export const { clearRestaurants } = restaurantsSlice.actions

export const selectRestaurantsList = (state) => state.restaurants.list
export const selectRestaurantsPagination = (state) => ({
  total: state.restaurants.total,
  page: state.restaurants.page,
  pageSize: state.restaurants.pageSize,
  pages: state.restaurants.pages,
})
export const selectRestaurantsListStatus = (state) => state.restaurants.listStatus
export const selectRestaurantById = (id) => (state) => state.restaurants.byId[id]
export const selectRestaurantDetailStatus = (state) => state.restaurants.detailStatus

export default restaurantsSlice.reducer
