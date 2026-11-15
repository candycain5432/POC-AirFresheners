"""Admin overview: money, the current goal, the open vote, the next meet, recent orders."""
from flask import render_template

from ...models import FreshenerCode, GarageMember, Order
from ...services.clock import shop_today
from ...services.fund import fund_summary
from ...services.meets import upcoming_meets
from ...services.voting import close_expired_rounds, current_round, round_results
from . import bp


@bp.route("/")
def dashboard():
    close_expired_rounds()
    open_round = current_round()
    upcoming = upcoming_meets(shop_today())
    return render_template(
        "admin/dashboard.html",
        fund=fund_summary(),
        open_round=open_round,
        results=round_results(open_round) if open_round else None,
        next_meet=upcoming[0] if upcoming else None,
        order_count=Order.query.filter_by(status="paid").count(),
        code_count=FreshenerCode.query.count(),
        member_count=GarageMember.query.count(),
        hidden_count=GarageMember.query.filter_by(is_hidden=True).count(),
        recent_orders=Order.query.filter_by(status="paid").order_by(Order.created_at.desc()).limit(8).all(),
    )
