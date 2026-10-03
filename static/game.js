document.addEventListener("DOMContentLoaded", () => {

    const posterGrid = document.getElementById("poster-grid");
    const puzzleDate = document.getElementById("puzzle-date");
    const userHeading = document.getElementById("user-heading");

    const modeLabel = document.getElementById("mode-label");
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");
    const footerText = document.getElementById("footer-text");

    const searchInput = document.getElementById("film-search");
    const selectedFilmId = document.getElementById("selected-film-id");
    const searchResults = document.getElementById("search-results");

    const guessForm = document.getElementById("guess-form");
    const guessButton = document.getElementById("guess-button");
    const guessFeedback = document.getElementById("guess-feedback");

    const scoreValue = document.getElementById("score-value");
    const scoreBar = document.getElementById("score-bar");

    const clueList = document.getElementById("clue-list");

    const winMessage = document.getElementById("win-message");
    const winTitle = document.getElementById("win-title");
    const winDescription = document.getElementById("win-description");

    const revealAnswerSection =
        document.getElementById("reveal-answer-section");

    const revealAnswerButton =
        document.getElementById("reveal-answer-button");

    const nextFilmSection =
        document.getElementById("next-film-section");

    const nextFilmButton =
        document.getElementById("next-film-button");

    const endlessButton =
        document.getElementById("endless-button");

    const helpButton =
        document.getElementById("help-button");

    const helpModal =
        document.getElementById("help-modal");

    const closeHelp =
        document.getElementById("close-help");

    const gotItButton =
        document.getElementById("got-it-button");


    let puzzle = null;
    let gameMode = "daily";
    let searchTimer = null;
    let selectedFilm = null;
    let gameOver = false;


    // --------------------------------------------------
    // Utility functions
    // --------------------------------------------------

    function escapeHTML(value) {
        return String(value ?? "").replace(
            /[&<>"']/g,
            character => ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            })[character]
        );
    }


    async function getJSON(url) {

        const response = await fetch(url);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Something went wrong."
            );
        }

        return data;
    }


    async function postJSON(url, body) {

        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(body)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Something went wrong."
            );
        }

        return data;
    }


    function setFeedback(message, type = "") {

        guessFeedback.textContent = message;
        guessFeedback.className = "feedback";

        if (type) {
            guessFeedback.classList.add(type);
        }
    }


    function updateScore(score) {

        const safeScore = Math.max(
            0,
            Math.min(1000, Number(score) || 0)
        );

        scoreValue.textContent = safeScore;

        scoreBar.style.width =
            `${safeScore / 10}%`;

        if (safeScore === 0 && !gameOver) {
            revealAnswerSection.classList.remove("hidden");
        } else {
            revealAnswerSection.classList.add("hidden");
        }
    }


    // --------------------------------------------------
    // Reset round UI
    // --------------------------------------------------

    function resetRoundUI() {

        gameOver = false;
        selectedFilm = null;

        clearTimeout(searchTimer);

        searchInput.value = "";
        searchInput.disabled = false;

        selectedFilmId.value = "";

        clearSearchResults();

        guessButton.disabled = true;
        guessButton.textContent = "Submit guess →";

        setFeedback("");

        winMessage.classList.add("hidden");

        winTitle.textContent = "Correct answer!";

        winDescription.textContent =
            "You found the missing film.";

        revealAnswerSection.classList.add("hidden");

        nextFilmSection.classList.add("hidden");

        userHeading.textContent =
            "Today's selection";

        if (revealAnswerButton) {
            revealAnswerButton.disabled = false;
            revealAnswerButton.textContent =
                "Reveal Answer";
        }
    }


    // --------------------------------------------------
    // Letterboxd profile
    // --------------------------------------------------

    function showProfileLink() {

        if (
            !puzzle ||
            !puzzle.username ||
            !puzzle.profile_url
        ) {
            userHeading.textContent =
                "Today's selection";

            return;
        }

        userHeading.innerHTML = `
            <a
                href="${escapeHTML(puzzle.profile_url)}"
                target="_blank"
                rel="noopener noreferrer"
                class="profile-link"
            >
                ${escapeHTML(puzzle.username)}'s Top 4
            </a>
        `;
    }


    // --------------------------------------------------
    // Poster rendering
    // --------------------------------------------------

    function renderPosters(films, hiddenSlot) {

        posterGrid.innerHTML = "";

        for (let slot = 0; slot < 4; slot++) {

            const card =
                document.createElement("div");

            card.className = "poster-card";

            if (slot === hiddenSlot) {

                card.innerHTML = `
                    <div class="poster-image-wrap">
                        <div class="poster-placeholder">
                            <span class="question-mark">?</span>
                            <span>MISSING FILM</span>
                        </div>
                    </div>

                    <p class="poster-title">
                        Unknown film
                    </p>

                    <p class="poster-year">
                        ????
                    </p>
                `;

            } else {

                const filmIndex =
                    slot < hiddenSlot
                        ? slot
                        : slot - 1;

                const film = films[filmIndex];

                if (!film) {

                    card.innerHTML = `
                        <div class="poster-image-wrap">
                            <div class="poster-placeholder">
                                <span class="question-mark">?</span>
                            </div>
                        </div>

                        <p class="poster-title">
                            Film unavailable
                        </p>
                    `;

                } else {

                    const poster = film.poster
                        ? `
                            <img
                                class="poster-image"
                                src="${escapeHTML(film.poster)}"
                                alt="${escapeHTML(film.title)} poster"
                                onerror="this.style.display='none'"
                            >
                        `
                        : `
                            <div class="poster-placeholder">
                                <span class="question-mark">▧</span>
                                <span>NO POSTER</span>
                            </div>
                        `;

                    card.innerHTML = `
                        <div class="poster-image-wrap">
                            ${poster}
                        </div>

                        <p class="poster-title">
                            ${escapeHTML(film.title)}
                        </p>

                        <p class="poster-year">
                            ${escapeHTML(film.year)}
                        </p>
                    `;
                }
            }

            posterGrid.appendChild(card);
        }
    }


    // --------------------------------------------------
    // Clue rendering
    // --------------------------------------------------

    function renderClues(clues) {

        clueList.innerHTML = "";

        if (!Array.isArray(clues) || clues.length === 0) {

            clueList.innerHTML =
                '<p class="loading-text">No clues are available.</p>';

            return;
        }

        clues.forEach(clue => {

            const item =
                document.createElement("div");

            item.className = "clue-item";
            item.dataset.key = clue.key;

            const button =
                document.createElement("button");

            button.type = "button";
            button.className = "clue-button";

            const name =
                document.createElement("span");

            name.className = "clue-name";
            name.textContent = clue.label;

            const cost =
                document.createElement("span");

            cost.className = "clue-cost";

            cost.textContent =
                clue.revealed
                    ? "Revealed"
                    : `−${clue.cost} pts`;

            button.append(name, cost);


            const content =
                document.createElement("div");

            content.className = "clue-content";


            if (clue.revealed) {

                content.textContent =
                    clue.value ||
                    "No information available.";

                item.classList.add("revealed");

                button.disabled = true;

            } else {

                content.classList.add("hidden");

                button.addEventListener(
                    "click",
                    () => revealClue(
                        clue,
                        item,
                        button,
                        cost,
                        content
                    )
                );
            }


            item.append(
                button,
                content
            );

            clueList.appendChild(item);
        });
    }


    async function revealClue(
        clue,
        item,
        button,
        costElement,
        content
    ) {

        if (gameOver || button.disabled) {
            return;
        }

        button.disabled = true;
        costElement.textContent = "Loading...";


        const endpoint =
            gameMode === "endless"
                ? "/api/endless/reveal"
                : "/api/reveal";


        try {

            const data =
                await postJSON(
                    endpoint,
                    {
                        clue: clue.key
                    }
                );


            content.textContent =
                data.value ||
                "No information available.";

            content.classList.remove("hidden");

            item.classList.add("revealed");

            costElement.textContent =
                "Revealed";


            updateScore(data.score);

        } catch (error) {

            setFeedback(
                error.message,
                "error"
            );

            button.disabled = false;

            costElement.textContent =
                `−${clue.cost} pts`;
        }
    }


    // --------------------------------------------------
    // Search
    // --------------------------------------------------

    function clearSearchResults() {

        searchResults.innerHTML = "";

        searchResults.classList.remove("open");
    }


    function clearSearch() {

        selectedFilm = null;

        selectedFilmId.value = "";

        searchInput.value = "";

        clearSearchResults();
    }


    function chooseFilm(film) {

        selectedFilm = film;

        selectedFilmId.value =
            film.id;

        searchInput.value =
            `${film.title} (${film.year})`;

        guessButton.disabled =
            gameOver;

        clearSearchResults();

        setFeedback("");
    }


    function renderSearchResults(films) {

        searchResults.innerHTML = "";

        if (!films.length) {

            searchResults.innerHTML =
                '<div class="no-results">No films found.</div>';

            searchResults.classList.add("open");

            return;
        }


        films.forEach(film => {

            const option =
                document.createElement("button");

            option.type = "button";
            option.className = "search-result";
            option.setAttribute(
                "role",
                "option"
            );

            option.innerHTML = `
                <span class="result-title">
                    ${escapeHTML(film.title)}
                </span>

                <span class="result-year">
                    ${escapeHTML(film.year)}
                </span>
            `;


            option.addEventListener(
                "mousedown",
                event => {

                    event.preventDefault();

                    chooseFilm(film);
                }
            );


            searchResults.appendChild(option);
        });


        searchResults.classList.add("open");
    }


    async function searchFilms(query) {

        try {

            const data =
                await getJSON(
                    `/api/search?q=${encodeURIComponent(query)}`
                );


            if (
                searchInput.value.trim() !==
                query
            ) {
                return;
            }


            renderSearchResults(
                data.results || data
            );

        } catch (error) {

            clearSearchResults();

            setFeedback(
                "Could not search films. Please try again.",
                "error"
            );
        }
    }


    searchInput.addEventListener(
        "input",
        () => {

            const query =
                searchInput.value.trim();

            selectedFilm = null;
            selectedFilmId.value = "";

            guessButton.disabled = true;

            setFeedback("");

            clearTimeout(searchTimer);


            if (query.length < 2) {

                clearSearchResults();

                return;
            }


            searchTimer =
                setTimeout(
                    () => searchFilms(query),
                    250
                );
        }
    );


    searchInput.addEventListener(
        "focus",
        () => {

            if (searchResults.children.length > 0) {
                searchResults.classList.add("open");
            }
        }
    );


    document.addEventListener(
        "click",
        event => {

            if (
                !event.target.closest(
                    ".search-wrapper"
                )
            ) {
                clearSearchResults();
            }
        }
    );


    // --------------------------------------------------
    // Guessing
    // --------------------------------------------------

    guessForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            if (
                !selectedFilm ||
                gameOver
            ) {
                return;
            }


            guessButton.disabled = true;
            guessButton.textContent =
                "Checking...";

            setFeedback("");


            const endpoint =
                gameMode === "endless"
                    ? "/api/endless/guess"
                    : "/api/guess";


            try {

                const data =
                    await postJSON(
                        endpoint,
                        {
                            film_id: selectedFilm.id
                        }
                    );


                updateScore(data.score);


                if (data.correct) {

                    clearSearch();

                    finishGame(
                        data.film,
                        data.score,
                        true
                    );

                } else {

                    setFeedback(
                        data.message ||
                        "That is not the missing film. Try again.",
                        "error"
                    );

                    guessButton.disabled = false;

                    guessButton.textContent =
                        "Submit guess →";

                    clearSearch();

                    if (Number(data.score) === 0) {

                        setFeedback(
                            "You're at 0 points. You can still guess, or reveal the answer.",
                            "error"
                        );
                    }
                }

            } catch (error) {

                setFeedback(
                    error.message,
                    "error"
                );

                guessButton.disabled = false;

                guessButton.textContent =
                    "Submit guess →";
            }
        }
    );


    // --------------------------------------------------
    // Finish game
    // --------------------------------------------------

    function finishGame(
    film,
    score,
    guessedCorrectly
) {

    gameOver = true;

    updateScore(score);

        searchInput.disabled = true;

        guessButton.disabled = true;

        guessButton.textContent =
            "Puzzle completed";


        if (guessedCorrectly) {

            setFeedback(
                "Correct! You found the missing film.",
                "success"
            );

            winTitle.textContent =
                "Correct answer!";

        } else {

            setFeedback(
                "The answer has been revealed.",
                "success"
            );

            winTitle.textContent =
                "The answer was...";
        }


        winDescription.textContent =
            `${film.title} (${film.year}) was the missing film.`;


        winMessage.classList.remove("hidden");


        revealAnswerSection.classList.add(
            "hidden"
        );


        showProfileLink();


        if (gameMode === "endless") {

            nextFilmSection.classList.remove(
                "hidden"
            );

        }


        const cards =
            posterGrid.querySelectorAll(
                ".poster-card"
            );

        const hiddenCard =
            cards[puzzle.hidden_slot];


        if (hiddenCard) {

            hiddenCard.innerHTML = `
                <div class="poster-image-wrap">
                    ${
                        film.poster
                            ? `
                                <img
                                    class="poster-image"
                                    src="${escapeHTML(film.poster)}"
                                    alt="${escapeHTML(film.title)} poster"
                                >
                            `
                            : `
                                <div class="poster-placeholder">
                                    <span class="question-mark">▧</span>
                                    <span>NO POSTER</span>
                                </div>
                            `
                    }
                </div>

                <p class="poster-title">
                    ${escapeHTML(film.title)}
                </p>

                <p class="poster-year">
                    ${escapeHTML(film.year)}
                </p>
            `;
        }


        clueList
            .querySelectorAll("button")
            .forEach(button => {
                button.disabled = true;
            });
            clearSearch();
    }


    // --------------------------------------------------
    // Reveal answer
    // --------------------------------------------------

    revealAnswerButton.addEventListener(
        "click",
        async () => {

            revealAnswerButton.disabled = true;
            revealAnswerButton.textContent =
                "Revealing...";


            const endpoint =
                gameMode === "endless"
                    ? "/api/endless/reveal-answer"
                    : "/api/reveal-answer";


            try {

                const data =
                    await postJSON(
                        endpoint,
                        {}
                    );


                finishGame(
                    data.film,
                    data.score,
                    false
                );

            } catch (error) {

                setFeedback(
                    error.message,
                    "error"
                );

                revealAnswerButton.disabled = false;

                revealAnswerButton.textContent =
                    "Reveal Answer";
            }
        }
    );


    // --------------------------------------------------
    // Endless mode
    // --------------------------------------------------

    endlessButton.addEventListener(
        "click",
        async () => {

            endlessButton.disabled = true;
            endlessButton.textContent =
                "Loading...";


            try {

                await postJSON(
                    "/api/endless/next",
                    {}
                );

                gameMode = "endless";

                resetRoundUI();

                await loadPuzzle();

                window.scrollTo({
                    top: 0,
                    behavior: "smooth"
                });

            } catch (error) {

                setFeedback(
                    error.message,
                    "error"
                );

            } finally {

                endlessButton.disabled = false;

                endlessButton.textContent =
                    "Endless";
            }
        }
    );


    nextFilmButton.addEventListener(
        "click",
        async () => {

            nextFilmButton.disabled = true;
            nextFilmButton.textContent =
                "Loading...";


            try {

                await postJSON(
                    "/api/endless/next",
                    {}
                );

                gameMode = "endless";

                resetRoundUI();

                await loadPuzzle();

                window.scrollTo({
                    top: 0,
                    behavior: "smooth"
                });

            } catch (error) {

                setFeedback(
                    error.message,
                    "error"
                );

            } finally {

                nextFilmButton.disabled = false;

                nextFilmButton.textContent =
                    "Next Film →";
            }
        }
    );


    // --------------------------------------------------
    // Help modal
    // --------------------------------------------------

    function showHelp() {
        helpModal.classList.remove("hidden");
    }


    function hideHelp() {
        helpModal.classList.add("hidden");
    }


    helpButton.addEventListener(
        "click",
        showHelp
    );

    closeHelp.addEventListener(
        "click",
        hideHelp
    );

    gotItButton.addEventListener(
        "click",
        hideHelp
    );


    helpModal.addEventListener(
        "click",
        event => {

            if (
                event.target === helpModal
            ) {
                hideHelp();
            }
        }
    );


    // --------------------------------------------------
    // Load puzzle
    // --------------------------------------------------

    async function loadPuzzle() {

        try {

            const endpoint =
                gameMode === "endless"
                    ? "/api/endless"
                    : "/api/puzzle";


            const data =
                await getJSON(endpoint);


            puzzle = data;


            if (gameMode === "endless") {

                modeLabel.textContent =
                    "ENDLESS MODE";

                pageTitle.textContent =
                    "Keep guessing.";

                pageSubtitle.textContent =
                    "A random Letterboxd user's favorite film is hidden. Find it and keep playing.";

                puzzleDate.textContent =
                    "ENDLESS · RANDOM PUZZLE";

                footerText.textContent =
                    "Keep playing forever.";

            } else {

                modeLabel.textContent =
                    "THE DAILY FOUR";

                pageTitle.textContent =
                    "Guess the missing film.";

                pageSubtitle.textContent =
                    "One film is missing from this Letterboxd user's Top 4. Use the clues to figure out which one.";

                puzzleDate.textContent =
                    `PUZZLE DATE · ${data.date}`;

                footerText.textContent =
                    "One puzzle every day.";
            }


            userHeading.textContent =
                "Today's selection";


            renderPosters(
                data.films || [],
                data.hidden_slot
            );


            renderClues(
                data.clues || []
            );


            updateScore(
                data.score
            );


            gameOver =
                data.won ||
                data.revealed_answer;


            searchInput.disabled =
                gameOver;

            guessButton.disabled =
                gameOver;


            winMessage.classList.add(
                "hidden"
            );


            nextFilmSection.classList.add(
                "hidden"
            );


            if (
                data.won ||
                data.revealed_answer
            ) {

                gameOver = true;

                searchInput.disabled = true;

                guessButton.disabled = true;

                guessButton.textContent =
                    "Puzzle completed";


                winMessage.classList.remove(
                    "hidden"
                );


                if (data.won) {

                    setFeedback(
                        "You've already solved this puzzle.",
                        "success"
                    );

                    winTitle.textContent =
                        "Puzzle completed!";

                    if (data.revealed_film) {

                        winDescription.textContent =
                            `${data.revealed_film.title} (${data.revealed_film.year}) was the missing film.`;

                        showProfileLink();

                        const cards =
                            posterGrid.querySelectorAll(
                                ".poster-card"
                            );

                        const hiddenCard =
                            cards[puzzle.hidden_slot];

                        if (hiddenCard) {

                            const film =
                                data.revealed_film;

                            hiddenCard.innerHTML = `
                                <div class="poster-image-wrap">
                                    ${
                                        film.poster
                                            ? `
                                                <img
                                                    class="poster-image"
                                                    src="${escapeHTML(film.poster)}"
                                                    alt="${escapeHTML(film.title)} poster"
                                                >
                                            `
                                            : `
                                                <div class="poster-placeholder">
                                                    <span class="question-mark">▧</span>
                                                    <span>NO POSTER</span>
                                                </div>
                                            `
                                    }
                                </div>

                                <p class="poster-title">
                                    ${escapeHTML(film.title)}
                                </p>

                                <p class="poster-year">
                                    ${escapeHTML(film.year)}
                                </p>
                            `;
                        }

                    } else {

                        winDescription.textContent =
                            "You already found the missing film.";
                    }

                } else {

                    setFeedback(
                        "The answer has been revealed.",
                        "success"
                    );

                    winTitle.textContent =
                        "Answer revealed";

                    if (data.revealed_film) {

                        winDescription.textContent =
                            `${data.revealed_film.title} (${data.revealed_film.year}) was the missing film.`;

                        showProfileLink();

                    } else {

                        winDescription.textContent =
                            "The answer was revealed.";
                    }
                }


                clueList
                    .querySelectorAll("button")
                    .forEach(button => {
                        button.disabled = true;
                    });


                if (gameMode === "endless") {

                    nextFilmSection.classList.remove(
                        "hidden"
                    );
                }


                return;
            }


            if (Number(data.score) === 0) {

                revealAnswerSection.classList.remove(
                    "hidden"
                );

            } else {

                revealAnswerSection.classList.add(
                    "hidden"
                );
            }


        } catch (error) {

            posterGrid.innerHTML = `
                <p class="feedback error">
                    Could not load the puzzle.
                    Check that the database has users
                    with four favorite films and that Flask is running.
                </p>
            `;

            clueList.innerHTML = "";

            setFeedback(
                error.message,
                "error"
            );
        }
    }


    // Start with the daily puzzle.
    loadPuzzle();

});