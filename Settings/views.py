from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.http.response import JsonResponse,HttpResponse
from .models import CostCategory,CostMaster
from Settings.models import Milestone,Task,phaseCategory,phases
from .forms import templates_milestone_form,templates_task_form
from django.db.models import F
import json
from Employee.models import PageGroup

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def list_templates(request):
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Settings").values_list('page__name',flat=True)
    return render(request,'list_templates.html',{"module":"settings","pageData":list(pageData)})
        
# loaddata
@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getTemplateData(request):
    projectType = "project"
    tasklist = CostMaster.objects.using('erp').values('id','name',milestone_name=F('cost_category__name'),milestone_id=F('cost_category__id'))
    if request.method == 'POST':
        cdict = {key:value for key,value in request.POST.items()}
        if 'mode' in cdict:
            if cdict['mode'] == "edit_table":
                if 'milestonename' in cdict:
                    milestone = Milestone.objects.get(pk = cdict['milstnid'])
                    milestone.name = cdict['milestonename']
                    milestone.save()
                else:
                    task = Task.objects.get(pk = cdict['tskid'])
                    task.name = cdict['taskname']                                         
                    task.save()
            if cdict['mode'] == "deletedata":
                if 'tskid' in cdict:
                    Task.objects.get(pk = cdict['tskid']).delete()
                else:
                    Milestone.objects.get(pk = cdict['milstnid']).delete()
        projectType = cdict['type']
        if projectType=="non_projects":
            tasklist= Milestone.objects.values('id','name','milestones__name','milestones__id')
        else:
            tasklist = CostMaster.objects.using('erp').values('id','name',milestone_name=F('cost_category__name'),milestone_id=F('cost_category__id'))
    return JsonResponse({'tasklist':list(tasklist),'projectType':projectType})

# Add Milestone
@csrf_exempt
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@login_required(login_url='home')
def add_milestone(request):
    if request.method == "POST":
        form = templates_milestone_form(request.POST)
        if form.is_valid():
            form.save()
            tasklist= Milestone.objects.values('id','name','milestones__name','milestones__id')
            return JsonResponse({"tasklist":list(tasklist)})
        else:
            print(form.errors)
            return JsonResponse({"Error":'Failed to save the task data'})

# Add Taks 
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_task(request):
    mid = request.POST.get('mid')
    if request.method == "POST":
        form = templates_task_form(request.POST)
        if form.is_valid():
            form_data = form.save(commit=False)
            milestone = Milestone.objects.get(pk=mid)
            form_data.mid = milestone
            form_data.save()
            tasklist= Milestone.objects.values('id','name','milestones__name','milestones__id')
            return JsonResponse({"tasklist":list(tasklist)})
        else:
            return JsonResponse({"Error":'Failed to save the task data'})
        
#.......................grouping costcategory

@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def groupingCostCategory(request):
    dropdownPhases = phases.objects.all()
    pageData = PageGroup.objects.filter(jobtitle_id = request.user.jobtitle_id , page__module__name = "Settings").values_list('page__name',flat=True)
    return render(request,'groupingmilestones.html',{"module":"settings","dropdownPhases":dropdownPhases,"pageData":list(pageData)})

# loaddata
@csrf_exempt
@login_required(login_url='home')
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def getListData(request):
    selectedGroup = 1
    if request.method == 'POST':
        cdict = {key:value for key,value in request.POST.items()}
        selectedGroup = cdict['type']
        if 'list1_activeIds' in cdict:
            milestonelist = []
            list1_activeIds = json.loads(cdict['list1_activeIds'])
            for item in list1_activeIds:
                milestonelist.append(phaseCategory(category = item,phases_id = selectedGroup))
            phaseCategory.objects.bulk_create(milestonelist)
        if 'list2_activeIds' in cdict:
            list2_activeIds = json.loads(cdict['list2_activeIds'])
            phaseCategory.objects.filter(category__in=list2_activeIds,phases_id = selectedGroup).delete()
    costCategoryList = CostCategory.objects.using('erp').values('id','name').order_by('name')
    groupedcostCategoryList = phaseCategory.objects.values('category').filter(phases__id = selectedGroup)
    return JsonResponse({'costCategoryList':list(costCategoryList),'groupedcostCategoryList':list(groupedcostCategoryList)})