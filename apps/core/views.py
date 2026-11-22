"""Trang chung tạm (Phase 2): trang chủ, giới thiệu."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    return render(request, "home.html")


@login_required
def about(request):
    return render(request, "about.html")
