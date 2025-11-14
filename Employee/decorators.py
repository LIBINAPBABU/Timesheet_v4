from django.http import response
from django.http.request import validate_host
from django.shortcuts import redirect,render,HttpResponse


def unathenticated(view_func):
    def wrapper_func(request,*args,**kwargs):
        if request.user.is_authenticated:
            return view_func(request,*args,**kwargs)
        else:
            return redirect('login')
    return wrapper_func

def allowedGroups(allowedgroup = []):
    def decoratorFunc(view_func):
        def wrapper_func(request,*args,**kwargs):
            group = None
            if request.user.groups.exists():
                # group = request.user.groups.all()[0].name
                group=request.user.groups.values_list('name',flat=True).all()
                # if group in allowedgroup:
                if set(group).intersection(allowedgroup):
                    return view_func(request,*args,**kwargs)
                else:
                    return HttpResponse("Sorry!! You are not Authorized")
        return wrapper_func
    return decoratorFunc