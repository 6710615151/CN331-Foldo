from django.urls import path

from . import views

app_name = "portfolios"

urlpatterns = [
    path("", views.portfolio_list, name="list"),
    path("new/", views.portfolio_create, name="create"),
    path("<int:pk>/preview/", views.portfolio_preview, name="preview"),
    path("<int:pk>/edit/", views.portfolio_edit, name="update"),
    path("<int:pk>/delete/", views.portfolio_delete, name="delete"),
    path("p/<slug:slug>/", views.portfolio_public, name="public"),
]
