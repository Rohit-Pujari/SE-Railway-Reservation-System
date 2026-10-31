from django.urls import path, re_path

from backend.app import django_views

urlpatterns = [
    path("api/csrf", django_views.csrf_token, name="csrf-token"),
    path("api/health", django_views.health_check, name="health"),
    path("api/health/db", django_views.database_health_check, name="database-health"),
    path("api/register", django_views.registration, name="register"),
    path("api/login", django_views.passenger_login, name="login"),
    path("api/session", django_views.passenger_session, name="session"),
    path("api/logout", django_views.passenger_logout, name="logout"),
    path("api/admin/login", django_views.admin_login, name="admin-login"),
    path("api/admin/logout", django_views.admin_logout, name="admin-logout"),
    path("api/admin/dashboard", django_views.admin_dashboard_data, name="admin-dashboard"),
    path("api/admin/trains/<int:train_id>", django_views.admin_train_update, name="admin-train-update"),
    path("api/travel-classes", django_views.travel_classes, name="travel-classes"),
    path("api/seats/availability", django_views.seat_availability, name="seat-availability"),
    path("api/stations", django_views.stations, name="stations"),
    path("api/trains/search", django_views.train_search, name="train-search"),
    path("api/bookings", django_views.booking_create, name="booking-create"),
    path("api/bookings/history", django_views.passenger_booking_history, name="booking-history"),
    path("api/bookings/status", django_views.passenger_booking_status, name="booking-status"),
    path("api/bookings/<int:booking_id>/cancel", django_views.passenger_booking_cancel, name="booking-cancel"),
    path("api/bookings/<int:booking_id>/passengers", django_views.booking_passenger_details, name="booking-passengers"),
    path("api/bookings/<int:booking_id>/fare", django_views.booking_fare, name="booking-fare"),
    path("", django_views.frontend, name="frontend"),
    re_path(r"^(?P<asset_path>assets/.+)$", django_views.frontend_asset, name="frontend-asset"),
]
