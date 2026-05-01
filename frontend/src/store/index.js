import { configureStore } from '@reduxjs/toolkit'
import authReducer from './slices/authSlice'
import restaurantsReducer from './slices/restaurantsSlice'
import reviewsReducer from './slices/reviewsSlice'
import favouritesReducer from './slices/favouritesSlice'
import ownerReducer from './slices/ownerSlice'

export const store = configureStore({
  reducer: {
    auth: authReducer,
    restaurants: restaurantsReducer,
    reviews: reviewsReducer,
    favourites: favouritesReducer,
    owner: ownerReducer,
  },
  devTools: true,
})
