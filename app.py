import os
import random
from datetime import date

from flask import Flask, jsonify, render_template, request, session
from dotenv import load_dotenv

from database import get_connection, create_daily_games_table


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise ValueError(
        "FLASK_SECRET_KEY is missing from your .env file."
    )

MAX_SCORE = 1000
MAX_FAVORITES = 4
WRONG_GUESS_COST = 10

CLUES = {
    "overview": {
        "label": "Plot",
        "cost": 200,
        "column": "overview",
    },
    "director": {
        "label": "Director",
        "cost": 150,
        "column": "director",
    },
    "actor_1": {
        "label": "Actor 1",
        "cost": 125,
        "column": "actor_1",
    },
    "actor_2": {
        "label": "Actor 2",
        "cost": 100,
        "column": "actor_2",
    },
    "actor_3": {
        "label": "Actor 3",
        "cost": 75,
        "column": "actor_3",
    },
    "tagline": {
        "label": "Tagline",
        "cost": 100,
        "column": "tagline",
    },
    "year": {
        "label": "Release year",
        "cost": 75,
        "column": "year",
    },
}


# --------------------------------------------------
# Date and session management
# --------------------------------------------------

def get_today():
    """Return today's date using the server's local date."""
    return date.today()


def sync_session_with_game(game):
    """
    Reset the player's daily clue and win state
    when the daily puzzle changes.
    """

    puzzle_date = game["date"]

    if session.get("puzzle_date") != puzzle_date:
        session["puzzle_date"] = puzzle_date
        session["revealed_clues"] = []
        session["wrong_guesses"] = 0
        session.pop("won_date", None)
        session.pop("revealed_answer_date", None)


def current_score():
    """Calculate the player's remaining daily score."""

    revealed = session.get("revealed_clues", [])
    wrong_guesses = session.get("wrong_guesses", 0)

    clue_deduction = sum(
        CLUES[key]["cost"]
        for key in revealed
        if key in CLUES
    )

    guess_deduction = wrong_guesses * WRONG_GUESS_COST

    return max(
        0,
        MAX_SCORE - clue_deduction - guess_deduction
    )


def game_is_won(game):
    """Check whether the player has solved today's puzzle."""

    return session.get("won_date") == game["date"]


def game_is_revealed(game):
    """Check whether the player has revealed today's answer."""

    return session.get("revealed_answer_date") == game["date"]


# --------------------------------------------------
# Endless mode session management
# --------------------------------------------------

def current_endless_score():
    """Calculate the player's remaining Endless score."""

    revealed = session.get("endless_revealed_clues", [])
    wrong_guesses = session.get("endless_wrong_guesses", 0)

    clue_deduction = sum(
        CLUES[key]["cost"]
        for key in revealed
        if key in CLUES
    )

    guess_deduction = wrong_guesses * WRONG_GUESS_COST

    return max(
        0,
        MAX_SCORE - clue_deduction - guess_deduction
    )


def endless_game_is_finished():
    """Check whether the current Endless round is finished."""

    return (
        session.get("endless_won", False)
        or session.get("endless_revealed", False)
    )


# --------------------------------------------------
# Daily puzzle selection
# --------------------------------------------------

def get_or_create_daily_game(cursor, puzzle_date):
    """
    Retrieve the puzzle for a date.

    If no puzzle exists for that date:
      1. Find users with exactly four distinct favorites.
      2. Randomly select one eligible user.
      3. Randomly select one of their favorite films.
      4. Save the puzzle in daily_games.
    """

    cursor.execute(
        """
        SELECT user_id, hidden_film_id
        FROM daily_games
        WHERE puzzle_date = %s
        """,
        (puzzle_date,),
    )

    existing_game = cursor.fetchone()

    if existing_game:
        return (
            existing_game["user_id"],
            existing_game["hidden_film_id"],
        )

    cursor.execute(
        """
        SELECT uf.user_id
        FROM user_favorites AS uf
        GROUP BY uf.user_id
        HAVING COUNT(DISTINCT uf.film_id) = %s
        """,
        (MAX_FAVORITES,),
    )

    eligible_users = [
        row["user_id"]
        for row in cursor.fetchall()
    ]

    if not eligible_users:
        return None

    selected_user_id = random.choice(eligible_users)

    cursor.execute(
        """
        SELECT film_id
        FROM user_favorites
        WHERE user_id = %s
        """,
        (selected_user_id,),
    )

    favorite_ids = [
        row["film_id"]
        for row in cursor.fetchall()
    ]

    if len(favorite_ids) != MAX_FAVORITES:
        return None

    hidden_film_id = random.choice(favorite_ids)

    cursor.execute(
        """
        INSERT INTO daily_games (
            puzzle_date,
            user_id,
            hidden_film_id
        )
        VALUES (%s, %s, %s)
        """,
        (
            puzzle_date,
            selected_user_id,
            hidden_film_id,
        ),
    )

    return selected_user_id, hidden_film_id


def get_daily_game():
    """Load today's puzzle and its four favorite films."""

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        puzzle_date = get_today()

        game = get_or_create_daily_game(
            cursor,
            puzzle_date,
        )

        connection.commit()

        if not game:
            return None

        user_id, hidden_film_id = game

        cursor.execute(
            """
            SELECT id, username, url
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

        user = cursor.fetchone()

        if not user:
            return None

        cursor.execute(
            """
            SELECT
                f.id,
                f.title,
                f.year,
                f.poster
            FROM user_favorites AS uf
            JOIN films AS f
                ON f.id = uf.film_id
            WHERE uf.user_id = %s
            """,
            (user_id,),
        )

        films = cursor.fetchall()

        if len(films) != MAX_FAVORITES:
            return None

        hidden_film = next(
            (
                film for film in films
                if film["id"] == hidden_film_id
            ),
            None,
        )

        if not hidden_film:
            return None

        return {
            "date": puzzle_date.isoformat(),
            "user": user,
            "films": films,
            "hidden_film_id": hidden_film_id,
        }

    finally:
        connection.close()


# --------------------------------------------------
# Endless puzzle selection
# --------------------------------------------------

def create_endless_game():
    """
    Create a completely random Endless puzzle.

    The game is stored in the user's Flask session,
    so every player can have their own Endless round.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT uf.user_id
            FROM user_favorites AS uf
            GROUP BY uf.user_id
            HAVING COUNT(DISTINCT uf.film_id) = %s
            """,
            (MAX_FAVORITES,),
        )

        eligible_users = [
            row["user_id"]
            for row in cursor.fetchall()
        ]

        if not eligible_users:
            return None

        selected_user_id = random.choice(eligible_users)

        cursor.execute(
            """
            SELECT
                f.id,
                f.title,
                f.year,
                f.poster
            FROM user_favorites AS uf
            JOIN films AS f
                ON f.id = uf.film_id
            WHERE uf.user_id = %s
            """,
            (selected_user_id,),
        )

        films = cursor.fetchall()

        if len(films) != MAX_FAVORITES:
            return None

        hidden_film = random.choice(films)

        return {
            "user": {
                "id": selected_user_id,
                "username": None,
                "url": None,
            },
            "films": films,
            "hidden_film_id": hidden_film["id"],
        }

    finally:
        connection.close()


def load_endless_game():
    """Load the current Endless game from the session."""

    user_id = session.get("endless_user_id")
    hidden_film_id = session.get("endless_hidden_film_id")

    if not user_id or not hidden_film_id:
        return None

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, username, url
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )

        user = cursor.fetchone()

        if not user:
            return None

        cursor.execute(
            """
            SELECT
                f.id,
                f.title,
                f.year,
                f.poster
            FROM user_favorites AS uf
            JOIN films AS f
                ON f.id = uf.film_id
            WHERE uf.user_id = %s
            """,
            (user_id,),
        )

        films = cursor.fetchall()

        if len(films) != MAX_FAVORITES:
            return None

        return {
            "user": user,
            "films": films,
            "hidden_film_id": hidden_film_id,
        }

    finally:
        connection.close()


def start_new_endless_round():
    """Start a fresh random Endless round."""

    game = create_endless_game()

    if not game:
        return None

    session["endless_user_id"] = game["user"]["id"]
    session["endless_hidden_film_id"] = game["hidden_film_id"]
    session["endless_revealed_clues"] = []
    session["endless_wrong_guesses"] = 0
    session["endless_won"] = False
    session["endless_revealed"] = False

    return load_endless_game()


# --------------------------------------------------
# Film search
# --------------------------------------------------

@app.route("/api/search")
def search_films():
    """Search the films table by title."""

    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify([])

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                title,
                year,
                poster
            FROM films
            WHERE title LIKE %s
            ORDER BY
                CASE
                    WHEN title LIKE %s THEN 0
                    ELSE 1
                END,
                title ASC,
                year ASC
            LIMIT 10
            """,
            (
                f"%{query}%",
                f"{query}%",
            ),
        )

        results = cursor.fetchall()

        return jsonify(results)

    finally:
        connection.close()


# --------------------------------------------------
# Main page
# --------------------------------------------------

@app.route("/")
def index():
    """Render the main game page."""
    return render_template("index.html")


# --------------------------------------------------
# Puzzle API
# --------------------------------------------------

@app.route("/api/puzzle")
def puzzle():
    """Return today's daily puzzle."""

    game = get_daily_game()

    if not game:
        return jsonify({
            "error": (
                "No eligible users with exactly four favorites "
                "were found in the database."
            )
        }), 404

    sync_session_with_game(game)

    hidden_film_id = game["hidden_film_id"]

    visible_films = [
        {
            "id": film["id"],
            "title": film["title"],
            "year": film["year"],
            "poster": film["poster"],
        }
        for film in game["films"]
        if film["id"] != hidden_film_id
    ]

    hidden_slot = next(
        index
        for index, film in enumerate(game["films"])
        if film["id"] == hidden_film_id
    )

    revealed = session.get("revealed_clues", [])

    clues = []

    for key, clue in CLUES.items():
        clues.append({
            "key": key,
            "label": clue["label"],
            "cost": clue["cost"],
            "revealed": key in revealed,
        })

    score = current_score()

    return jsonify({
        "mode": "daily",
        "date": game["date"],
        "username": game["user"]["username"],
        "profile_url": game["user"]["url"],
        "films": visible_films,
        "hidden_slot": hidden_slot,
        "score": score,
        "clues": clues,
        "won": game_is_won(game),
        "revealed_answer": game_is_revealed(game),
        "can_reveal_answer": score == 0,
    })


# --------------------------------------------------
# Endless Puzzle API
# --------------------------------------------------

@app.route("/api/endless")
def endless():
    """Return the current Endless puzzle or create one."""

    game = load_endless_game()

    if not game:
        game = start_new_endless_round()

    if not game:
        return jsonify({
            "error": (
                "No eligible users with exactly four favorites "
                "were found in the database."
            )
        }), 404

    hidden_film_id = game["hidden_film_id"]

    visible_films = [
        {
            "id": film["id"],
            "title": film["title"],
            "year": film["year"],
            "poster": film["poster"],
        }
        for film in game["films"]
        if film["id"] != hidden_film_id
    ]

    hidden_slot = next(
        index
        for index, film in enumerate(game["films"])
        if film["id"] == hidden_film_id
    )

    revealed = session.get("endless_revealed_clues", [])

    clues = []

    for key, clue in CLUES.items():
        clues.append({
            "key": key,
            "label": clue["label"],
            "cost": clue["cost"],
            "revealed": key in revealed,
        })

    score = current_endless_score()

    return jsonify({
        "mode": "endless",
        "username": game["user"]["username"],
        "profile_url": game["user"]["url"],
        "films": visible_films,
        "hidden_slot": hidden_slot,
        "score": score,
        "clues": clues,
        "won": session.get("endless_won", False),
        "revealed_answer": session.get("endless_revealed", False),
        "can_reveal_answer": score == 0,
    })


@app.route("/api/endless/next", methods=["POST"])
def endless_next():
    """Start another random Endless round."""

    game = start_new_endless_round()

    if not game:
        return jsonify({
            "error": (
                "No eligible users with exactly four favorites "
                "were found in the database."
            )
        }), 404

    return jsonify({
        "success": True
    })


# --------------------------------------------------
# Reveal clue API
# --------------------------------------------------

@app.route("/api/reveal", methods=["POST"])
def reveal_clue():
    """Reveal a clue for the daily puzzle."""

    data = request.get_json(silent=True) or {}
    clue_key = data.get("clue")

    if clue_key not in CLUES:
        return jsonify({
            "error": "Invalid clue."
        }), 400

    game = get_daily_game()

    if not game:
        return jsonify({
            "error": "No puzzle is available."
        }), 404

    sync_session_with_game(game)

    if game_is_won(game) or game_is_revealed(game):
        return jsonify({
            "error": "This puzzle has already ended."
        }), 400

    revealed = session.get("revealed_clues", [])

    if clue_key in revealed:
        return jsonify({
            "error": "This clue has already been revealed."
        }), 400

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                title,
                year,
                tagline,
                overview,
                director,
                actor_1,
                actor_2,
                actor_3
            FROM films
            WHERE id = %s
            """,
            (game["hidden_film_id"],)
        )

        film = cursor.fetchone()

    finally:
        connection.close()

    if not film:
        return jsonify({
            "error": "The hidden film could not be found."
        }), 404

    column = CLUES[clue_key]["column"]
    value = film.get(column)

    if value is None or str(value).strip() == "":
        return jsonify({
            "error": "This clue is unavailable for this film."
        }), 400

    revealed.append(clue_key)
    session["revealed_clues"] = revealed

    return jsonify({
        "key": clue_key,
        "label": CLUES[clue_key]["label"],
        "value": value,
        "cost": CLUES[clue_key]["cost"],
        "score": current_score(),
    })


# --------------------------------------------------
# Endless clue API
# --------------------------------------------------

@app.route("/api/endless/reveal", methods=["POST"])
def endless_reveal_clue():
    """Reveal a clue for the current Endless puzzle."""

    data = request.get_json(silent=True) or {}
    clue_key = data.get("clue")

    if clue_key not in CLUES:
        return jsonify({
            "error": "Invalid clue."
        }), 400

    game = load_endless_game()

    if not game:
        return jsonify({
            "error": "No Endless puzzle is available."
        }), 404

    if endless_game_is_finished():
        return jsonify({
            "error": "This Endless round has already ended."
        }), 400

    revealed = session.get("endless_revealed_clues", [])

    if clue_key in revealed:
        return jsonify({
            "error": "This clue has already been revealed."
        }), 400

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                title,
                year,
                tagline,
                overview,
                director,
                actor_1,
                actor_2,
                actor_3
            FROM films
            WHERE id = %s
            """,
            (game["hidden_film_id"],)
        )

        film = cursor.fetchone()

    finally:
        connection.close()

    if not film:
        return jsonify({
            "error": "The hidden film could not be found."
        }), 404

    column = CLUES[clue_key]["column"]
    value = film.get(column)

    if value is None or str(value).strip() == "":
        return jsonify({
            "error": "This clue is unavailable for this film."
        }), 400

    revealed.append(clue_key)
    session["endless_revealed_clues"] = revealed

    return jsonify({
        "key": clue_key,
        "label": CLUES[clue_key]["label"],
        "value": value,
        "cost": CLUES[clue_key]["cost"],
        "score": current_endless_score(),
    })


# --------------------------------------------------
# Reveal Answer API
# --------------------------------------------------

@app.route("/api/reveal-answer", methods=["POST"])
def reveal_answer():
    """Reveal the daily puzzle answer when the player reaches zero."""

    game = get_daily_game()

    if not game:
        return jsonify({
            "error": "No puzzle is available."
        }), 404

    sync_session_with_game(game)

    if game_is_won(game):
        return jsonify({
            "error": "You have already solved this puzzle."
        }), 400

    if current_score() > 0:
        return jsonify({
            "error": "You can reveal the answer once your score reaches 0."
        }), 400

    session["revealed_answer_date"] = game["date"]

    film = get_film_by_id(game["hidden_film_id"])

    if not film:
        return jsonify({
            "error": "The hidden film could not be found."
        }), 404

    return jsonify({
        "correct": True,
        "film": film,
        "score": 0,
        "message": "The answer has been revealed."
    })


@app.route("/api/endless/reveal-answer", methods=["POST"])
def endless_reveal_answer():
    """Reveal the Endless answer when the player reaches zero."""

    game = load_endless_game()

    if not game:
        return jsonify({
            "error": "No Endless puzzle is available."
        }), 404

    if endless_game_is_finished():
        return jsonify({
            "error": "This Endless round has already ended."
        }), 400

    if current_endless_score() > 0:
        return jsonify({
            "error": "You can reveal the answer once your score reaches 0."
        }), 400

    session["endless_revealed"] = True

    film = get_film_by_id(game["hidden_film_id"])

    if not film:
        return jsonify({
            "error": "The hidden film could not be found."
        }), 404

    return jsonify({
        "correct": True,
        "film": film,
        "score": 0,
        "message": "The answer has been revealed."
    })


# --------------------------------------------------
# Guess API
# --------------------------------------------------

def get_film_by_id(film_id):
    """Get basic film information by ID."""

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                id,
                title,
                year,
                poster
            FROM films
            WHERE id = %s
            """,
            (film_id,),
        )

        return cursor.fetchone()

    finally:
        connection.close()


@app.route("/api/guess", methods=["POST"])
def submit_guess():
    """Check a player's guess for the daily puzzle."""

    data = request.get_json(silent=True) or {}

    try:
        guessed_film_id = int(data.get("film_id"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Select a film from the search results."
        }), 400

    game = get_daily_game()

    if not game:
        return jsonify({
            "error": "No puzzle is available."
        }), 404

    sync_session_with_game(game)

    if game_is_won(game) or game_is_revealed(game):
        return jsonify({
            "error": "This puzzle has already ended."
        }), 400

    if guessed_film_id == game["hidden_film_id"]:
        session["won_date"] = game["date"]

        film = get_film_by_id(game["hidden_film_id"])

        return jsonify({
            "correct": True,
            "film": film,
            "score": current_score(),
            "message": "Correct! You found the missing film.",
        })

    session["wrong_guesses"] = session.get(
        "wrong_guesses",
        0
    ) + 1

    score = current_score()

    return jsonify({
        "correct": False,
        "score": score,
        "message": "Not quite. −10 points. Try another film.",
    })


# --------------------------------------------------
# Endless Guess API
# --------------------------------------------------

@app.route("/api/endless/guess", methods=["POST"])
def submit_endless_guess():
    """Check a player's guess for the current Endless puzzle."""

    data = request.get_json(silent=True) or {}

    try:
        guessed_film_id = int(data.get("film_id"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Select a film from the search results."
        }), 400

    game = load_endless_game()

    if not game:
        return jsonify({
            "error": "No Endless puzzle is available."
        }), 404

    if endless_game_is_finished():
        return jsonify({
            "error": "This Endless round has already ended."
        }), 400

    if guessed_film_id == game["hidden_film_id"]:
        session["endless_won"] = True

        film = get_film_by_id(game["hidden_film_id"])

        return jsonify({
            "correct": True,
            "film": film,
            "score": current_endless_score(),
            "message": "Correct! You found the missing film.",
        })

    session["endless_wrong_guesses"] = session.get(
        "endless_wrong_guesses",
        0
    ) + 1

    score = current_endless_score()

    return jsonify({
        "correct": False,
        "score": score,
        "message": "Not quite. −10 points. Try another film.",
    })


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.route("/api/health")
def health():
    """Check whether Flask can connect to MySQL."""

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()

        return jsonify({
            "status": "ok",
            "database": "connected",
        })

    finally:
        connection.close()


# --------------------------------------------------
# Start application
# --------------------------------------------------

if __name__ == "__main__":
    create_daily_games_table()
    app.run(debug=True)