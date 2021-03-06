# -*- coding: utf-8 -*-

from datetime import datetime
import pytz
import pdb
from dateutil import relativedelta

from openerp import models
from openerp import fields
from openerp import api
from openerp import exceptions
from openerp import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

_STATES = [
    ("new", "New"),
    ("approve", "Approved"),
    ("open", "Open"),
    ("done", "Done")
]

class OpenacademyTags(models.Model):
    """OpenAcademy Tags"""
    _name = "openacademy.tags"

    name = fields.Char(string="Tag Name", required=True)
    active = fields.Boolean(stirng="Archived", default=True)
    color = fields.Integer(string="Color Index")

class OpenacademyCourse(models.Model):
    """OpenAcademy Course"""

    _name = "openacademy.course"

    name = fields.Char(string="Course Name", required=True)
    responsible_id = fields.Many2one(comodel_name="res.users", string="Responsible", required=True)
    active = fields.Boolean(stirng="Archived", default=True)
    notes = fields.Html(string="Notes")
    code = fields.Char(string="Code", size=16)
    session_ids = fields.One2many(comodel_name="openacademy.session", inverse_name="course_id", string="Sesions")
    session_count = fields.Integer(compute="_compute_session_count", store=True, string="Session Count")

    @api.multi
    @api.depends("session_ids")
    def _compute_session_count(self):
        for record in self:
            record.session_count = len(record.session_ids)

    @api.multi
    def name_get(self):
        vals = []
        for record in self:
            vals.append((record.id, "[{}] {}".format(record.code, record.name)))
        return vals

class openacademy_session(models.Model):
    """Open Academy Session"""

    _name = "openacademy.session"

    name = fields.Char(string="Session Title", size=200, \
                        translate=True, required=True, copy=False)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(stirng="Archived", default=True)
    code = fields.Char(string="Code", size=16)
    max_seat = fields.Integer(string="Maximum Avaiable Seats", required=True,\
                                 default=10, index=True)
    min_seat = fields.Integer(string="Minimum Required Seats", required=True, index=True)
    duration_days = fields.Float(string="Duration(days)", digits=(6,3),\
                                 required=True, default=1)
    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")
    is_public = fields.Boolean(string="Is Public Event ?")
    notes = fields.Text(string="Notes")
    contain = fields.Html(string="Session Course")
    banner = fields.Binary(string="Banner")
    state  = fields.Selection(string="State", selection=_STATES, default="new")
    instructor_id = fields.Many2one(comodel_name="res.partner", string="Instructor", domain="[('supplier', '=', True)]")
    course_id = fields.Many2one(comodel_name="openacademy.course", string="Course", required=True)
    tag_ids = fields.Many2many(comodel_name="openacademy.tags", relation="rel_session_tags", column1="session_id", column2="tag_id", string="Tags")
    attendee_ids = fields.One2many(comodel_name="openacademy.attendee", inverse_name="session_id", string="Attendees")
    total_invited = fields.Integer(compute="count_total_invited", string="Total Invited")
    total_attneding = fields.Integer(compute="count_total_invited", string="Total Attending")


    _sql_constraints = [
        ("session_code_unique", "unique (code)", _("The code must ne unique !")),
    ]

    @api.multi
    @api.depends("attendee_ids")
    def count_total_invited(self):
        for record in self:
            self.total_invited = sum([att.count for att in record.attendee_ids ])
            self.total_attneding = sum([att.count for att in record.attendee_ids if att.state == "going"])

    @api.constrains("start_date", "end_date")
    def date_validation(self):
        if self.start_date > self.end_date:
            local = self.env.context.get("tz") and pytz.timezone(self.env.context.get("tz")) or "UTC"
            start_date = datetime.strptime(self.start_date, DEFAULT_SERVER_DATETIME_FORMAT)
            local_date = local.localize(start_date, is_dst=None)
            # pdb.set_trace()
            raise exceptions.ValidationError(_("Session start date: %s should not be after end date: %s.")%(local_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT+ " %Z"), self.end_date))

    @api.model
    def create(self, vals):
        if vals.get("code"):
            records = self.search([("code", "=", vals.get("code"))])
            if records:
                raise exceptions.ValidationError("Code must have ot be unique in instance")
        res = super(openacademy_session, self).create(vals)
        #ugly code
        if not res.code:
            res.code = res.name[:16].upper()
        return res

    @api.onchange("start_date")
    def onchange_start_date(self):
        start_date = datetime.strptime(self.start_date, DEFAULT_SERVER_DATETIME_FORMAT)
        end_date = start_date + relativedelta.relativedelta(days=self.duration_days)
        self.end_date = end_date


class OpenacademyAttendee(models.Model):
    """OpenAcademy Attendee"""

    _name = "openacademy.attendee"

    name = fields.Char(string="Attendee Name", required=True)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")
    email = fields.Char(string="Email")
    count = fields.Integer(string="Invited Individual")
    session_id = fields.Many2one(comodel_name="openacademy.session", string="Session")
    state = fields.Selection(string="Status", selection=[("invite", "Invited"), ("going", "Going to Attned"), ("not", "Not Attending"), ("unsure", "Unsure")], default="invite")

    @api.onchange("partner_id")
    def oc_partner(self):
        if self.partner_id:
            self.write({
                "email": self.partner_id.email,
                "name": self.partner_id.name,
            })
            # self.email = self.partner_id.email
            # self.name = self.partner_id.name