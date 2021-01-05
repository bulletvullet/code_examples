from django.conf import settings
from django.db.models import Case, Count, F, Sum, Value, When
from django_filters import rest_framework
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from contents.models import Block

from .filters import DashboardEmailFilter, DashboardSmsFilter
from .models import MailKey, SmsElephantHistory
from .serializers import *


class DashboardView(viewsets.GenericViewSet):
    """Analytical dashboard viewset."""

    filterset_class = DashboardEmailFilter
    filter_backends = (rest_framework.DjangoFilterBackend,)

    serializer_classes = {
        "reconnects": DashboardRecconectsSerializer,
        "openings": DashboardOpeningsSerializer,
        "keywords": DashboardKeywordsSerializer,
        "products": DashboardProductsSerializer,
        "pos_reconnects": DashboardPosReconnectsSerializer,
        "clicks": DashboardClicksSerializer,
    }

    def get_queryset(self):
        queryset = MailKey.objects.filter(
            point_of_sales__brand__user=self.request.user,
            customer_relation__isnull=False,
        )
        return self.filter_queryset(queryset)

    def get_serializer_class(self):
        return self.serializer_classes.get(self.action)

    @action(methods=["get"], detail=False, url_path="reconnects")
    def reconnects(self, request, *args, **kwargs):
        """Count different types of the reconnects."""

        serializer_class = self.get_serializer_class()
        queryset = self.get_queryset()
        return Response(
            serializer_class(
                queryset.aggregate(
                    client=Count(Case(When(client=True, then=Value(1)))),
                    prospect=Count(Case(When(prospect=True, then=Value(1)))),
                    speciale=Count(Case(When(speciale=True, then=Value(1)))),
                )
            ).data
        )

    @action(methods=["get"], detail=False, url_path="openings")
    def openings(self, request, *args, **kwargs):
        """Get openings data for sms and emails."""

        #  sms data
        qs = SmsElephantHistory.objects.filter(brand_id=self.request.user.id)
        sms_queryset = DashboardSmsFilter(request.GET, qs).qs.aggregate(
            sms=Count("visits")
        )

        # email data
        serializer_class = self.get_serializer_class()
        queryset = self.get_queryset()

        # combine sms and emails
        return Response(
            serializer_class(
                {**queryset.aggregate(email=Count("count_opened")), **sms_queryset}
            ).data
        )

    @action(methods=["get"], detail=False, url_path="keywords")
    def keywords(self, request, *args, **kwargs):
        """Get summary usage info for the keywords."""

        query_limit = 10
        serializer_class = self.get_serializer_class()
        queryset = self.get_queryset()
        return Response(
            serializer_class(
                queryset.filter(customer_relation__keywords__id__isnull=False)
                .prefetch_related("customer_relation__keywords")
                .annotate(name=F("customer_relation__keywords__name"))
                .values("name")
                .annotate(count=Count("customer_relation__keywords__id"))
                .order_by("-count")[:query_limit],
                many=True,
            ).data
        )

    @action(methods=["get"], detail=False, url_path="products")
    def products(self, request, *args, **kwargs):
        """Get the summary usage info by the products."""

        query_limit = 10
        serializer_class = self.get_serializer_class()
        queryset = self.get_queryset()
        return Response(
            serializer_class(
                queryset.filter(customer_relation__products__id__isnull=False)
                .prefetch_related("customer_relation__products")
                .annotate(
                    name=F("customer_relation__products__name"),
                    thumbnail=F("customer_relation__products__thumbnail"),
                )
                .values("name", "thumbnail")
                .annotate(count=Count("customer_relation__products__id"))
                .order_by("-count")[:query_limit],
                context={"request": self.request},
                many=True,
            ).data
        )

    @action(methods=["get"], detail=False, url_path="pos-reconnects")
    def pos_reconnects(self, request, *args, **kwargs):
        """Get summary productivity info for the sales points."""

        serializer_class = self.get_serializer_class()
        queryset = self.get_queryset()
        return Response(
            serializer_class(
                queryset.values("point_of_sales", "point_of_sales__name")
                .annotate(
                    name=F("point_of_sales__name"),
                    reconnects=Count("id"),
                    openings=Sum("count_opened"),
                    clicks=Sum("clicks_count"),
                )
                .values("name", "reconnects", "openings", "clicks")
                .order_by("-reconnects", "-openings", "-clicks"),
                many=True,
            ).data
        )

    @action(methods=["get"], detail=False, url_path="clicks")
    def clicks(self, request, *args, **kwargs):
        """Get summary clicks info."""

        queryset = self.get_queryset().exclude(clicks={})
        # get all blocks for brand
        blocks = list(
            Block.objects.exclude(addedContent=[])
            .filter(brand=self.request.user)
            .values("addedContent", "selectedContent")
        )
        # get unique phones of point_of_sales for adding custom call and itinerary blocks on-the-fly
        # because we don't have those blocks on the backend.
        for point_of_sales in (
            queryset.select_related("point_of_sales")
            .filter(point_of_sales__phone__isnull=False)
            .annotate(
                phone=F("point_of_sales__phone"),
                pos_url=F("point_of_sales__url_google_map"),
            )
            .distinct("phone")
            .values("phone", "pos_url")
        ):
            blocks.extend(
                [
                    {
                        "selectedContent": "Itinerary",
                        "addedContent": [{"link": point_of_sales["pos_url"]}],
                    },
                    {
                        "selectedContent": "Call",
                        "addedContent": [
                            {
                                "link": f"https://{settings.DOMAIN}/phone-call?phone={point_of_sales['phone']}"
                            }
                        ],
                    },
                ]
            )
        data = {}
        # go through the mail_keys with clicked lings
        for m in queryset:
            for link in m.clicks:
                # get only first matched block and break blocks list for exclude duplicates
                already_processed = False
                # go through all available blocks
                for block in blocks:
                    if already_processed:
                        break
                    for added_content in block["addedContent"]:
                        # check if link key is in block
                        if "link" not in added_content:
                            continue
                        # check that clicked link same link as in added content
                        if link == added_content["link"]:
                            # upcount amount if used blocks
                            if block["selectedContent"] in data:
                                data[block["selectedContent"]] += 1
                            else:
                                data[block["selectedContent"]] = 1
                            already_processed = True
        return Response(self.get_serializer_class()(data).data)
