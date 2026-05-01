import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import {
  getReviews as apiList,
  createReview as apiCreate,
  updateReview as apiUpdate,
  deleteReview as apiDelete,
} from '../../api/restaurants'

export const fetchReviews = createAsyncThunk(
  'reviews/list',
  async ({ restaurantId, page = 1, pageSize = 20 }, { rejectWithValue }) => {
    try {
      const { data } = await apiList(restaurantId, { page, page_size: pageSize })
      return { restaurantId, ...data }
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || 'Failed to load reviews')
    }
  },
)

export const submitReview = createAsyncThunk(
  'reviews/create',
  async ({ restaurantId, payload }, { rejectWithValue }) => {
    try {
      const { data } = await apiCreate(restaurantId, payload)
      return { restaurantId, ack: data, clientPayload: payload }
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || 'Review submission failed')
    }
  },
)

export const updateReviewThunk = createAsyncThunk(
  'reviews/update',
  async ({ restaurantId, reviewId, payload }, { rejectWithValue }) => {
    try {
      const { data } = await apiUpdate(restaurantId, reviewId, payload)
      return { reviewId, ack: data }
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || 'Review update failed')
    }
  },
)

export const deleteReviewThunk = createAsyncThunk(
  'reviews/delete',
  async ({ restaurantId, reviewId }, { rejectWithValue }) => {
    try {
      const { data } = await apiDelete(restaurantId, reviewId)
      return { reviewId, ack: data }
    } catch (err) {
      return rejectWithValue(err.response?.data?.detail || 'Review delete failed')
    }
  },
)

const reviewsSlice = createSlice({
  name: 'reviews',
  initialState: {
    byRestaurant: {},
    status: 'idle',
    error: null,
    submitStatus: 'idle',
    submitError: null,
    pendingEvents: [],
  },
  reducers: {
    clearSubmitStatus(state) {
      state.submitStatus = 'idle'; state.submitError = null
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchReviews.pending, (s) => { s.status = 'loading'; s.error = null })
      .addCase(fetchReviews.fulfilled, (s, a) => {
        s.status = 'succeeded'
        s.byRestaurant[a.payload.restaurantId] = {
          items: a.payload.items || [],
          total: a.payload.total || 0,
          page: a.payload.page || 1,
          pages: a.payload.pages || 0,
        }
      })
      .addCase(fetchReviews.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload })
      .addCase(submitReview.pending, (s) => { s.submitStatus = 'loading'; s.submitError = null })
      .addCase(submitReview.fulfilled, (s, a) => {
        s.submitStatus = 'accepted'
        s.pendingEvents.push({
          type: 'review.created',
          restaurantId: a.payload.restaurantId,
          at: Date.now(),
        })
      })
      .addCase(submitReview.rejected, (s, a) => { s.submitStatus = 'failed'; s.submitError = a.payload })
      .addCase(updateReviewThunk.fulfilled, (s, a) => {
        s.pendingEvents.push({ type: 'review.updated', reviewId: a.payload.reviewId, at: Date.now() })
      })
      .addCase(deleteReviewThunk.fulfilled, (s, a) => {
        s.pendingEvents.push({ type: 'review.deleted', reviewId: a.payload.reviewId, at: Date.now() })
      })
  },
})

export const { clearSubmitStatus } = reviewsSlice.actions

export const selectReviewsFor = (restaurantId) => (state) =>
  state.reviews.byRestaurant[restaurantId] || { items: [], total: 0, page: 1, pages: 0 }
export const selectReviewsStatus = (state) => state.reviews.status
export const selectSubmitStatus = (state) => state.reviews.submitStatus
export const selectSubmitError = (state) => state.reviews.submitError
export const selectPendingReviewEvents = (state) => state.reviews.pendingEvents

export default reviewsSlice.reducer
