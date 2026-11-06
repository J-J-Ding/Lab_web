from django.utils import timezone
from .models import DETAIL_MODELS
from .site_context import is_team


def asset_data(asset):
    if asset.scan_status!='CLEAN' or asset.deletion_requested_at or (asset.expires_at and asset.expires_at<=timezone.now()):return None
    return {'id':str(asset.pk),'mime_type':asset.mime_type,'size':asset.size,'url':f'/api/{"site" if is_team() else "public"}/assets/{asset.pk}/'}


def cover_for_revision(revision):
    if not revision:return None
    links=sorted(revision.assets.all(),key=lambda link:(link.position,str(link.pk)))
    eligible=[link for link in links if link.asset.mime_type.startswith('image/') and link.asset.scan_status=='CLEAN' and not link.asset.deletion_requested_at and (not link.asset.expires_at or link.asset.expires_at>timezone.now())]
    return next((link.asset for link in eligible if link.purpose=='cover'),next((link.asset for link in eligible if link.purpose=='image'),None))


def member_data(profile):
    r=profile.published_revision
    result={'id':str(profile.pk),'slug':r.slug,'display_name':r.display_name,
        'member_kind':r.member_kind,'public_member_status':r.public_member_status,'enrollment_year':r.enrollment_year,
        'research_areas':[l.area.name for l in r.research_links.all()],
        'education':[{'education_level':e.education_level} for e in r.education.all() if e.education_level]}
    if r.public_contact_email:result['public_contact_email']=r.public_contact_email
    result['avatar']=asset_data(r.avatar_asset) if r.avatar_asset_id else None
    return result


def content_data(item):
    r=item.published_revision
    detail=getattr(r,DETAIL_MODELS[item.kind]._meta.get_field('revision').remote_field.related_name)
    # Explicit exclusion from the typed model; account/private tables are never traversed.
    data={f.name:getattr(detail,f.name) for f in detail._meta.fields if f.name not in ('revision','funding_amount')}
    # URL content is rendered only after a browser-side protocol check.
    people=[]
    for c in r.contributions.all():
        p=c.contributor.member_profile
        public=p and (p.user_id is None or (p.user.is_active and p.user.role in ('TEACHER','STUDENT'))) and not (p.user_id and p.user.is_superuser) and p.merged_into_id is None and p.published_revision_id and p.published_revision.state=='PUBLISHED' and p.published_revision.public_member_status in ('ACTIVE','ALUMNI')
        name=p.published_revision.display_name if public else ('团队成员' if p and p.user_id else c.approved_display_name)
        people.append({'name':name,'affiliation':c.approved_affiliation,'position':c.position,
            'role':c.contribution_role,'is_corresponding':c.is_corresponding,'member_slug':p.published_revision.slug if public else None})
    cover=cover_for_revision(r)
    return {'cover':asset_data(cover) if cover else None,'id':str(item.pk),'kind':item.kind,'revision':str(r.pk),'title':r.title,'summary':r.summary,
        'date':item.public_date,'detail':data,'contributions':people,
        'projects':[{'id':str(l.target_project_id),'title':l.target_project.published_revision.title} for l in r.project_links.all()],
        'assets':[d for link in r.assets.all() if (d:=asset_data(link.asset))]}
