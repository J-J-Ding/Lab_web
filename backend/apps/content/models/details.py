from django.db import models
from django.db.models import Q,F
from .base import ContentRevision


class PaperDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='paper')
    doi=models.CharField(max_length=255,blank=True)
    venue=models.CharField(max_length=300,blank=True)
    publication_date=models.DateField(null=True,blank=True)
    category=models.CharField(max_length=80,blank=True)
    volume=models.CharField(max_length=40,blank=True)
    issue=models.CharField(max_length=40,blank=True)
    pages=models.CharField(max_length=40,blank=True)
    open_url=models.URLField(max_length=1000,blank=True)


class ProjectDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='project')
    project_number=models.CharField(max_length=255,blank=True)
    funder=models.CharField(max_length=200,blank=True)
    level=models.CharField(max_length=100,blank=True)
    start_date=models.DateField(null=True,blank=True)
    end_date=models.DateField(null=True,blank=True)
    status=models.CharField(max_length=16,choices=[('ACTIVE','ACTIVE'),('COMPLETED','COMPLETED'),('CANCELLED','CANCELLED')],default='ACTIVE')
    funding_amount=models.DecimalField(max_digits=16,decimal_places=2,null=True,blank=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(start_date__isnull=True)|Q(end_date__isnull=True)|Q(end_date__gte=F('start_date')),name='project_date_order'),models.CheckConstraint(condition=Q(funding_amount__isnull=True)|Q(funding_amount__gte=0),name='project_funding_positive'),models.CheckConstraint(condition=Q(status__in=['ACTIVE','COMPLETED','CANCELLED']),name='project_status_valid')]


class AwardDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='award')
    event_name=models.CharField(max_length=300,blank=True)
    category=models.CharField(max_length=32,choices=[('COMPETITION','COMPETITION'),('HONOR','HONOR')],default='COMPETITION')
    level=models.CharField(max_length=100,blank=True)
    award_name=models.CharField(max_length=200,blank=True)
    award_date=models.DateField(null=True,blank=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(category__in=['COMPETITION','HONOR']),name='award_category_valid')]


class ActivityDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='activity')
    starts_at=models.DateTimeField(null=True,blank=True)
    ends_at=models.DateTimeField(null=True,blank=True)
    location=models.CharField(max_length=300,blank=True)
    body=models.TextField(blank=True,max_length=50000)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(starts_at__isnull=True)|Q(ends_at__isnull=True)|Q(ends_at__gte=F('starts_at')),name='activity_date_order')]


class NewsDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='news')
    body=models.TextField(blank=True,max_length=50000)
    event_date=models.DateField(null=True,blank=True)
    category=models.CharField(max_length=100,blank=True)


class BlogDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='blog')
    body=models.TextField(blank=True,max_length=50000)
    event_date=models.DateField(null=True,blank=True)
    category=models.CharField(max_length=100,blank=True)


class PublicationDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='publication')
    isbn=models.CharField(max_length=255,blank=True)
    publisher=models.CharField(max_length=200,blank=True)
    publication_date=models.DateField(null=True,blank=True)
    edition=models.CharField(max_length=100,blank=True)


class LabPageDetail(models.Model):
    revision=models.OneToOneField(ContentRevision,on_delete=models.CASCADE,primary_key=True,related_name='lab_page')
    page_key=models.CharField(max_length=8,choices=[('home','home'),('about','about'),('contact','contact')])
    body=models.TextField(blank=True,max_length=50000)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(page_key__in=['home','about','contact']),name='lab_page_key_valid')]


DETAIL_MODELS={'PAPER':PaperDetail,'PROJECT':ProjectDetail,'AWARD':AwardDetail,'ACTIVITY':ActivityDetail,'NEWS':NewsDetail,'BLOG':BlogDetail,'PUBLICATION':PublicationDetail,'LAB_PAGE':LabPageDetail}
