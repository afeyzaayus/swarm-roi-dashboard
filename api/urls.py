from django.urls import path
from . import views

urlpatterns = [
    path("sim/start", views.sim_start),
    path("sim/state", views.sim_state),
    path("sim/stop", views.sim_stop),
    path("sim/obstacle", views.obstacle_move),
    path("scenarios", views.scenarios),
    path("roi", views.roi),
]
