# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from Settings.models import CostMaster,CostCategory
from Employee.models import users
from django.db.models.deletion import CASCADE
from django.utils import timezone

class IcproProject(models.Model):
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(unique=True, max_length=50)
    name = models.CharField(unique=True, max_length=100)
    status = models.CharField(max_length=10)
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    version_lock = models.BigIntegerField(blank=True, null=True)
    project_engineer_name = models.CharField(max_length=200, blank=True, null=True)
    project_engineer_id = models.BigIntegerField(blank=True, null=True)
    project_manager_name = models.CharField(max_length=200, blank=True, null=True)
    project_manager_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'icpro_project'

class CostSpecification(models.Model):
    id = models.BigIntegerField(primary_key=True)
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    version_lock = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cost_specification'
        unique_together = (('code', 'name'),)

class Customer(models.Model):
    id = models.BigIntegerField(primary_key=True)
    business_value = models.FloatField(blank=True, null=True)
    code = models.CharField(unique=True, max_length=10)
    company_website = models.CharField(max_length=200, blank=True, null=True)
    customer_type = models.CharField(max_length=25, blank=True, null=True)
    industry_domain = models.CharField(max_length=255, blank=True, null=True)
    industry_domain_name = models.CharField(max_length=100, blank=True, null=True)
    is_internation = models.TextField(blank=True, null=True)  # This field type is a guess.
    name = models.CharField(unique=True, max_length=255)
    status = models.CharField(max_length=10)
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    version_lock = models.BigIntegerField(blank=True, null=True)
    customer_manager_id = models.BigIntegerField(blank=True, null=True)
    bom_margin_percentage = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'customer'

class Quotation(models.Model):
    id = models.BigIntegerField(primary_key=True)
    about_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    architecture_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    bom_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    company_profile = models.TextField(blank=True, null=True)
    covering_letter = models.TextField(blank=True, null=True)
    letter_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    covering_letter_subject = models.CharField(max_length=255, blank=True, null=True)
    draft_no = models.CharField(max_length=40, blank=True, null=True)
    parent_quotation_id = models.BigIntegerField(blank=True, null=True)
    price_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    project_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    quotation_no = models.CharField(max_length=40, blank=True, null=True)
    quote_date = models.DateTimeField()
    quote_expiry_date = models.DateTimeField()
    quote_value = models.FloatField(blank=True, null=True)
    remarks = models.CharField(max_length=1000, blank=True, null=True)
    revision_number = models.IntegerField(blank=True, null=True)
    sale_type = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    supply_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    version_lock = models.BigIntegerField(blank=True, null=True)
    work_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    project = models.ForeignKey(IcproProject, models.DO_NOTHING, blank=True, null=True)
    bom_price_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    repeated_quote = models.ForeignKey('self', models.DO_NOTHING, blank=True, null=True)
    repeated = models.CharField(max_length=50, blank=True, null=True)
    bom_partno_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    bom_material_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    bom_qty_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    bom_rate_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    bom_group_by_category = models.TextField(blank=True, null=True)  # This field type is a guess.
    header_image_country_id = models.BigIntegerField(blank=True, null=True)
    header_image_location_id = models.BigIntegerField(blank=True, null=True)
    quote_discount_value = models.BigIntegerField(blank=True, null=True)
    quote_discount_type = models.CharField(max_length=255, blank=True, null=True)
    quote_discount_amount = models.BigIntegerField(blank=True, null=True)
    enquiry_number = models.CharField(max_length=200, blank=True, null=True)
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    cost_group = models.CharField(max_length=200, blank=True, null=True)
    custom_group = models.TextField(blank=True, null=True)  # This field type is a guess.
    cost_category_group = models.CharField(max_length=200, blank=True, null=True)
    system_name = models.CharField(max_length=255, blank=True, null=True)
    total_service_pricing_label = models.CharField(max_length=255, blank=True, null=True)
    total_supply_pricing_label = models.CharField(max_length=255, blank=True, null=True)
    total_service_price = models.FloatField(blank=True, null=True)
    total_supply_price = models.FloatField(blank=True, null=True)
    total_pricing_label = models.CharField(max_length=255, blank=True, null=True)
    bom_group_pricing_description = models.CharField(max_length=255, blank=True, null=True)
    system_architecture_header_name = models.CharField(max_length=400, blank=True, null=True)
    table_header_background_color = models.CharField(max_length=100, blank=True, null=True)
    table_footer_background_color = models.CharField(max_length=100, blank=True, null=True)
    bom_lumpsum = models.TextField(blank=True, null=True)  # This field type is a guess.
    engservice_pricelumpsum = models.TextField(blank=True, null=True)  # This field type is a guess.
    total_lumpsum = models.TextField(blank=True, null=True)  # This field type is a guess.
    bom_specifications_show_me = models.TextField(blank=True, null=True)  # This field type is a guess.
    custom_project_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'quotation'
        unique_together = (('quotation_no', 'revision_number'),)

class QuotationCost(models.Model):
    id = models.BigIntegerField(primary_key=True)
    cost_name = models.CharField(max_length=255, blank=True, null=True)
    cost_specification_name = models.CharField(max_length=255, blank=True, null=True)
    exchange_rate = models.FloatField(blank=True, null=True)
    net_amount = models.FloatField(blank=True, null=True)
    quantity = models.FloatField(blank=True, null=True)
    selling_pricing = models.FloatField(blank=True, null=True)
    create_date = models.DateTimeField()
    create_user = models.CharField(max_length=50)
    create_user_id = models.BigIntegerField()
    last_updated_date = models.DateTimeField()
    last_updated_user = models.CharField(max_length=50)
    last_updated_user_id = models.BigIntegerField()
    tax_amount = models.FloatField(blank=True, null=True)
    tax_percentage = models.FloatField(blank=True, null=True)
    total_price = models.FloatField(blank=True, null=True)
    version_lock = models.BigIntegerField(blank=True, null=True)
    cost = models.ForeignKey(CostMaster, models.DO_NOTHING, blank=True, null=True)
    cost_specification = models.ForeignKey(CostSpecification, models.DO_NOTHING, blank=True, null=True)
    quotation = models.ForeignKey(Quotation, models.DO_NOTHING, blank=True, null=True)
    custom_group_name = models.CharField(max_length=200, blank=True, null=True)
    table_group_name = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    category_grouping = models.CharField(max_length=200, blank=True, null=True)
    pricing_label = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'quotation_cost'
# tsm model
class AssignedQuotation(models.Model):
    quotation = models.CharField(max_length=50, null=False, default=None)
    user = models.ForeignKey(users, on_delete=models.CASCADE, db_index=True)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['quotation']),
            models.Index(fields=['user', 'quotation']),
        ]

# class AssignedMilestone(models.Model):
#     user = models.ForeignKey(users, on_delete=models.CASCADE, default=None, db_index=True)
#     quotation = models.CharField(max_length=50, null=False, db_index=True)
#     project = models.IntegerField(null=True, db_index=True,default=None)  # Allow null values and index
#     projectName = models.CharField(max_length=100, null=True,default=None)
#     milestone = models.IntegerField(null=True, db_index=True,default=None)  # Allow null values and index
#     milestoneName = models.CharField(max_length=100, null=True)
#     task = models.IntegerField(null=True, db_index=True,default=None)  # Allow null values and index
#     taskName = models.CharField(max_length=100, null=True)
#     user = models.ForeignKey(users, on_delete=models.CASCADE, default=None, db_index=True)
#     start_date = models.DateField(default=timezone.now, null=False)
#     end_date = models.DateField(default=timezone.now, null=False)
#     created_date = models.DateTimeField(auto_now_add=True)
#     updated_date = models.DateTimeField(auto_now=True)

#     class Meta:
#         indexes = [
#             models.Index(fields=['quotation', 'milestone']),
#             models.Index(fields=['user', 'quotation']),
#             models.Index(fields=['user', 'start_date', 'end_date']),
#         ]

# Newly Added
#------------------------------------------------------------------------------------------------#
class AssignedTask(models.Model):
    assignBy = models.ForeignKey(
        users, on_delete=models.CASCADE, related_name='assignBy',
        db_index=True, blank=True, null=True
    )
    assignTo = models.ForeignKey(
        users, on_delete=models.CASCADE, related_name='assignTo',
        db_index=True, blank=True, null=True
    )
    quotation = models.CharField(max_length=50, db_index=True)
    customprojectName = models.CharField(max_length=100, blank=True, null=True, default=None)
    systemName = models.CharField(max_length=100, blank=True, null=True, default=None)
    customerName = models.CharField(max_length=100, blank=True, null=True, default=None)
    customerCode = models.CharField(max_length=25, blank=True, null=True, default=None)
    quoted_date = models.DateField(default=timezone.now)
    
    project = models.IntegerField(db_index=True, blank=True, null=True, default=None)
    projectName = models.CharField(max_length=100, blank=True, null=True, default=None)
    milestone = models.IntegerField(db_index=True, blank=True, null=True, default=None)
    milestoneName = models.CharField(max_length=100, blank=True, null=True)
    task = models.IntegerField(db_index=True, blank=True, null=True, default=None)
    taskName = models.CharField(max_length=100, blank=True, null=True)
    
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(default=timezone.now)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['quotation', 'milestone']),
            models.Index(fields=['assignTo', 'quotation']),
            models.Index(fields=['assignTo', 'start_date', 'end_date']),
            models.Index(fields=['assignTo', 'project', 'milestone', 'task']),  # helpful for filtering tasks
        ]
        verbose_name = "Assigned Task"
        verbose_name_plural = "Assigned Tasks"

class Submission(models.Model):
    assignId = models.ForeignKey(AssignedTask, on_delete=models.CASCADE, db_index=True)
    date = models.DateField()
    hours = models.PositiveIntegerField(default=0)
    rate = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=50, blank=True, null=True, default=None)
    rejection_reason = models.TextField(blank=True, null=True, default=None)

    approvedBy = models.ForeignKey(
        users, on_delete=models.CASCADE, related_name='approvedBy',
        db_index=True, blank=True, null=True
    )
    approved_status = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['assignId', 'date']),
            models.Index(fields=['assignId', 'status']),
        ]
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"

#------------------------------------------------------------------------------------------------#
# 
#         
# class TimesheetSubmission(models.Model):
#     uid = models.ForeignKey(users, on_delete=CASCADE, db_index=True)  # Add index on uid
#     quotation = models.CharField(max_length=50, null=False, db_index=True, default=None)
#     project = models.IntegerField(null=True, db_index=True, default=None)  # Allow null values and index
#     projectName = models.CharField(max_length=100, null=True, default=None)
#     milestone = models.IntegerField(db_index=True, default=None, null=True)  # Index on milestone
#     milestoneName = models.CharField(max_length=100, null=False, default=None)
#     task = models.IntegerField(null=True, db_index=True, default=None)
#     taskName = models.CharField(max_length=100, null=False, default=None)
#     date = models.DateField(default=None)
#     hours = models.IntegerField(default=None)
#     created_date = models.DateTimeField(auto_now_add=True)
#     submission_date = models.DateTimeField(auto_now_add=True)
#     timesheet_status = models.CharField(max_length=50, default=None, null=True)
#     rejection_reason = models.CharField(max_length=1000, default=None, null=True)
#     rate = models.IntegerField(default=0)

#     class Meta:
#         indexes = [
#             models.Index(fields=['uid', 'quotation']),  # Composite index for uid and quotation
#             models.Index(fields=['uid', 'milestone']),  # Composite index for uid and milestone
#         ]

class TimesheetStatus(models.Model):
    STATUS_CHOICES = [
        ('Requested', ''),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    ]
    uid = models.ForeignKey(users, on_delete=CASCADE, db_index=True)  # Add index on uid
    timesheet_status = models.CharField(max_length=50, default=None, null=True)
    weeknumber = models.IntegerField(default=None, null=True, db_index=True)  # Index for frequent filtering
    submission_status = models.BooleanField(default=False)
    action_status = models.BooleanField(default=False)
    weekyear = models.IntegerField(default=None, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    # action_by = models.ForeignKey(users,related_name='timesheet_statuses_action_by', on_delete=CASCADE)  # Add index on uid
    unlock_reason = models.CharField(max_length=1000, default=None, null=True)
    # unlock_request = models.BooleanField(default=False)
    unlock_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=None, null=True)
    updated_date = models.DateTimeField(auto_now=True)
    comments = models.CharField(max_length=1000, blank=True, null=True, default=None)
    
    class Meta:
        indexes = [
            models.Index(fields=['uid', 'weeknumber']),  # Composite index for uid and weeknumber
        ]

