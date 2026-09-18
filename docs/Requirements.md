# Problem Statement

Build a Agentic Meal Planner where I can build my personal or family profile, requirements, diet, kitchen stock and generate a customized plan which refreshes as per a pre defined cadence.

## Goal, Scope & Success Criteria

The meal planner should be able to do following items:
1. On first signup of a new user, it should leverage llms and build a complete profile asking all basic biological details, dietary preferences, medical history and save it. It should also let a user create a family group where existing users can be added. 
2. It should have a view to add every food item present in user's home - 
    Groceries - Category wise like, Spices/Grains/Pulses etc
    Veggies
    Fruits
    Any other category?
3. Based on view selected (single/family), preferences saved and available items in the kitchen it should update the users daily and weekly meal plan. Exclude the complexity of considering quantities. 
4. Users should be able to add a new meal which is added in a database/memory which will be used to suggest future options.


## Architecture Preferences/Constraints

No constraints, use the best tools as per requirements.
Use best agentic ai framework if needed.
LLM will be used from GROQ. API Key will be added after development
This will be a web as well as mobile app. Mobile app will be in React Native. 


## Appearance:
Appearance should be modern yet simple, it should not resemble typical llm generated apps.
Simple light and dark mode theme. 

## Deployment and usability
Ability to deploy and use through public urls, like vercel or render.

## Note:
Goals, requirements are reference. Come up with a unique idea based on above guidelines.
Understand the core idea and suggest any features that will make this app even more usable