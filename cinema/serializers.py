from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from cinema.models import (
    Genre,
    Actor,
    CinemaHall,
    Movie,
    MovieSession,
    Ticket,
    Order
)


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "first_name", "last_name", "full_name")


class CinemaHallSerializer(serializers.ModelSerializer):
    class Meta:
        model = CinemaHall
        fields = ("id", "name", "rows", "seats_in_row", "capacity")


class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ("id", "title", "description", "duration", "genres", "actors")


class MovieListSerializer(MovieSerializer):
    genres = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="name"
    )
    actors = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="full_name"
    )


class MovieDetailSerializer(MovieSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    actors = ActorSerializer(many=True, read_only=True)

    class Meta:
        model = Movie
        fields = ("id", "title", "description", "duration", "genres", "actors")


class MovieSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovieSession
        fields = ("id", "show_time", "movie", "cinema_hall")


class MovieSessionListSerializer(MovieSessionSerializer):
    movie_title = serializers.CharField(source="movie.title", read_only=True)
    cinema_hall_name = serializers.CharField(
        source="cinema_hall.name", read_only=True
    )
    cinema_hall_capacity = serializers.IntegerField(
        source="cinema_hall.capacity", read_only=True
    )
    tickets_available = serializers.IntegerField(read_only=True)

    class Meta:
        model = MovieSession
        fields = (
            "id",
            "show_time",
            "movie_title",
            "cinema_hall_name",
            "cinema_hall_capacity",
            "tickets_available",
        )


class TicketSerializer(serializers.ModelSerializer):
    movie_session = serializers.PrimaryKeyRelatedField(queryset=MovieSession.objects.all())

    class Meta:
        model = Ticket
        fields = ("id", "movie_session", "row", "seat")

    def validate(self, attrs):
        movie_session = attrs.get("movie_session")
        row = attrs.get("row")
        seat = attrs.get("seat")

        if not movie_session:
            raise serializers.ValidationError(
                {"movie_session": "Movie session is required to validate row and seat."}
            )

        cinema_hall = movie_session.cinema_hall

        for ticket_attr_value, ticket_attr_name, cinema_hall_attr_name in [
            (row, "row", "rows"),
            (seat, "seat", "seats_in_row"),
        ]:
            count_attrs = getattr(cinema_hall, cinema_hall_attr_name)
            if not (1 <= ticket_attr_value <= count_attrs):
                raise serializers.ValidationError(
                    {
                        ticket_attr_name: f"{ticket_attr_name} "
                        f"number must be in available range: "
                        f"(1, {cinema_hall_attr_name}): "
                        f"(1, {count_attrs})"
                    }
                )
        return attrs


class MovieSessionDetailSerializer(MovieSessionSerializer):
    movie = MovieListSerializer(many=False, read_only=True)
    cinema_hall = CinemaHallSerializer(many=False, read_only=True)
    taken_places = serializers.SerializerMethodField()

    class Meta:
        model = MovieSession
        fields = ("id", "show_time", "movie", "cinema_hall", "taken_places")

    def get_taken_places(self, obj):
        return [
            {"row": ticket.row, "seat": ticket.seat}
            for ticket in obj.tickets.all()
        ]


class OrderSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=False, allow_empty=False)

    class Meta:
        model = Order
        fields = ("id", "created_at", "tickets")
        validators = [
            UniqueTogetherValidator(
                queryset=Ticket.objects.all(),
                fields=["movie_session", "row", "seat"]
            )
        ]

    def create(self, validated_data):
        with transaction.atomic():
            tickets_data = validated_data.pop("tickets")
            order = Order.objects.create(**validated_data)
            for ticket_data in tickets_data:
                Ticket.objects.create(order=order, **ticket_data)
            return order


class TicketListSerializer(TicketSerializer):
    movie_session = MovieSessionListSerializer(read_only=True)


class OrderListSerializer(OrderSerializer):
    tickets = TicketListSerializer(read_only=True, many=True)
