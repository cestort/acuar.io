from django.urls import path

from . import views

app_name = "aquarium"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("mediciones/nueva/", views.measurement_add, name="measurement_add"),
    path("mediciones/<int:pk>/editar/", views.measurement_edit, name="measurement_edit"),
    path("mediciones/<int:pk>/borrar/", views.measurement_delete, name="measurement_delete"),
    path("parametros/", views.parameter_list, name="parameter_list"),
    path("parametros/nuevo/", views.parameter_form, name="parameter_create"),
    path("parametros/<int:pk>/", views.parameter_detail, name="parameter_detail"),
    path("parametros/<int:pk>/editar/", views.parameter_form, name="parameter_edit"),
    path("diario/", views.maintenance_list, name="maintenance_list"),
    path("diario/nueva/", views.maintenance_form, name="maintenance_create"),
    path("diario/<int:pk>/editar/", views.maintenance_form, name="maintenance_edit"),
    path("diario/<int:pk>/borrar/", views.maintenance_delete, name="maintenance_delete"),
]
