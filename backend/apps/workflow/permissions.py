from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from apps.accounts.permissions import is_manager
from apps.accounts.services import locked_users
from apps.content.models import ContentItem,ContentRevision
from apps.content.services import locked_editor
from .models import ContentEditGrant


def actor_for(request, manager=False, editor=False):
    actor,_=locked_users(request)
    if manager and not is_manager(actor):
        raise PermissionDenied()
    if editor:
        actor=locked_editor(actor)
    return actor


def visible_items(actor):
    qs=ContentItem.objects.all()
    if not is_manager(actor):
        grants=ContentEditGrant.objects.filter(user=actor,revoked_at__isnull=True).values('item_id')
        qs=qs.filter(Q(created_by=actor)|Q(pk__in=grants))
    return qs.order_by('-updated_at','id')


def can_edit(actor,item):
    return is_manager(actor) or item.created_by_id==actor.pk or ContentEditGrant.objects.filter(item=item,user=actor,can_edit=True,revoked_at__isnull=True).exists()


def locked_item(actor,pk,edit=False):
    item=get_object_or_404(visible_items(actor).select_for_update(),pk=pk)
    if edit and not can_edit(actor,item):
        raise PermissionDenied('This collaboration is read-only.')
    return item


def locked_revision(actor,pk,edit=False):
    ref=get_object_or_404(ContentRevision.objects.only('item_id'),pk=pk)
    item=locked_item(actor,ref.item_id,edit)
    revision=get_object_or_404(ContentRevision.objects.select_for_update(),pk=pk,item=item)
    return item,revision



def can_submit(actor):
    from apps.members.models import MemberProfile
    return is_manager(actor) or (actor.role=='STUDENT' and MemberProfile.objects.filter(user=actor,membership_status='ACTIVE',merged_into__isnull=True).exists())


def selectable_contributors(actor):
    from django.db.models import Case,When,F,Value,CharField,OuterRef,Subquery
    from apps.content.models import Contributor,RevisionContribution
    from apps.content.selectors import published_content
    qs=Contributor.objects.all()
    if is_manager(actor):return qs.annotate(safe_name=F('display_name'),safe_affiliation=F('external_affiliation'))
    published=published_content().values('published_revision_id')
    signatures=RevisionContribution.objects.filter(contributor_id=OuterRef('pk'),revision_id__in=published).order_by('-revision__created_at','pk')
    public_ids=RevisionContribution.objects.filter(revision_id__in=published).values('contributor_id')
    owned=Q(created_by=actor,member_profile__isnull=True)|Q(member_profile__user=actor)
    public_member=Q(member_profile__public_visible=True,member_profile__published_revision__state='PUBLISHED',member_profile__published_revision__public_member_status__in=['ACTIVE','ALUMNI'])
    return qs.filter(owned|public_member|Q(pk__in=public_ids)).annotate(
        safe_name=Case(When(owned,then=F('display_name')),When(public_member,then=F('member_profile__published_revision__display_name')),default=Subquery(signatures.values('approved_display_name')[:1]),output_field=CharField()),
        safe_affiliation=Case(When(owned,then=F('external_affiliation')),When(public_member,then=Value('')),default=Subquery(signatures.values('approved_affiliation')[:1]),output_field=CharField())).distinct()
