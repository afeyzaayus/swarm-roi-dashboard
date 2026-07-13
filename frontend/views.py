from django.shortcuts import render


def index(request):
    return render(request, "index.html")


def roi_page(request):
    return render(request, "roi.html")
