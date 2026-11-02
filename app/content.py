"""Original practice prompts in IELTS format."""

TASK2_QUESTIONS = [
    "Some people believe that university students should pay the full cost of their studies, while others think "
    "higher education should be free. Discuss both views and give your own opinion.",
    "In many cities, people now work from home several days a week. Do the advantages of this trend outweigh the disadvantages?",
    "Some people think that governments should invest more in public transport than in building new roads. "
    "To what extent do you agree or disagree?",
    "Children today spend more time on screens than playing outdoors. What are the causes of this, and what can be done about it?",
    "Many young people in developing countries move to big cities for work. Is this a positive or negative development?",
    "Some say that learning a foreign language is a waste of time now that translation apps are so good. "
    "To what extent do you agree or disagree?",
    "Tourism brings money to local communities but can also damage the environment and local culture. "
    "How can these problems be reduced?",
    "Some people believe that the best way to reduce crime is to give longer prison sentences. Others think there are "
    "better ways. Discuss both views and give your opinion.",
    # two-part (direct) questions
    "More and more people are choosing to live alone. Why is this happening? Is it a positive or negative development?",
    "Many people now buy most of their goods online rather than in local shops. What effects does this have on towns "
    "and cities? What can be done to support local businesses?",
    "Some children are given a lot of free time, while others have every hour of the day planned by their parents. "
    "Which approach is better for children? What problems might the other approach cause?",
]

# General Training Task 1: letter, three bullet points, at least 150 words, ~20 minutes
_LETTER_TAIL = "\n\nWrite at least 150 words. You do NOT need to write any addresses.\n\nBegin your letter as follows:\n\n"
GT_LETTERS = [
    "You recently bought a kitchen appliance online, but it stopped working after one week.\n\n"
    "Write a letter to the company. In your letter\n• describe what you bought and how you bought it\n"
    "• explain what the problem is\n• say what you would like the company to do" + _LETTER_TAIL + "Dear Sir or Madam,",
    "You would like to change your working hours for the next three months.\n\n"
    "Write a letter to your manager. In your letter\n• explain why you need to change your hours\n"
    "• say what hours you would like to work\n• suggest how your work will still be done" + _LETTER_TAIL + "Dear Mr Clarke,",
    "A friend is going to visit your city for the first time next month and has asked for your advice.\n\n"
    "Write a letter to your friend. In your letter\n• recommend somewhere to stay\n"
    "• describe two places they should visit\n• give some advice about getting around the city" + _LETTER_TAIL + "Dear Sam,",
    "Your neighbours have been making a lot of noise late at night for several weeks.\n\n"
    "Write a letter to your neighbours. In your letter\n• explain who you are\n"
    "• describe the problem and how it affects you\n• suggest a solution" + _LETTER_TAIL + "Dear Neighbours,",
    "You saw an advertisement for a part-time evening course at a local college, but you need more information.\n\n"
    "Write a letter to the college. In your letter\n• say which course you are interested in and why\n"
    "• ask about the timetable and the cost\n• ask what you need to do to join" + _LETTER_TAIL + "Dear Sir or Madam,",
    "You recently stayed with a friend for a weekend while you were travelling.\n\n"
    "Write a letter to your friend. In your letter\n• thank them for having you to stay\n"
    "• say what you enjoyed most about the weekend\n• invite them to visit you" + _LETTER_TAIL + "Dear Alex,",
]

SPEAKING_QUESTIONS = {
    "part1": [
        "Do you work or are you a student? What do you like most about it?",
        "Tell me about the area where you live. Has it changed much recently?",
        "How often do you use your phone to learn new things?",
        "Do you prefer cooking at home or eating out? Why?",
        "What kind of music do you enjoy listening to, and when?",
        "Is there a sport you would like to try in the future?",
    ],
    "part2": [
        "Describe a skill you learned that took a long time. You should say: what the skill is, when you started, "
        "how you learned it, and explain why it took so long.",
        "Describe a place in your city you like to visit. You should say: where it is, how often you go, what you do there, "
        "and explain why you like it.",
        "Describe a time you helped someone. You should say: who you helped, what the problem was, how you helped, "
        "and explain how you felt afterwards.",
    ],
    "part3": [
        "Why do you think some people find it hard to keep studying after they finish school?",
        "How has technology changed the way young people make friends?",
        "Should governments spend more money on public parks than on shopping centres? Why?",
        "Do you think artificial intelligence will make language learning easier or harder?",
    ],
}
