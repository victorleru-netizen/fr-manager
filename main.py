import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading

# Charger les variables d'environnement (pour le token)
load_dotenv()

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Initialisation de Flask pour maintenir le bot actif
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Fichier pour stocker les avis
AVIS_FILE = "avis.json"

# Charger les avis existants
def load_avis():
    if os.path.exists(AVIS_FILE):
        with open(AVIS_FILE, "r") as f:
            return json.load(f)
    return {}

# Sauvegarder les avis
def save_avis(avis):
    with open(AVIS_FILE, "w") as f:
        json.dump(avis, f, indent=4)

avis_data = load_avis()

# Fonction pour vérifier si un membre est un staff
def est_staff(member: discord.Member) -> bool:
    # Remplace ces IDs par ceux des rôles "staff" de ton serveur
    roles_staff = [
        123456789012345678,  # ID du rôle "Modérateur"
        987654321098765432   # ID du rôle "Administrateur"
    ]
    return any(role.id in roles_staff for role in member.roles)

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.tree.command(name="avis", description="Laisser un avis sur un membre du staff")
async def avis(interaction: discord.Interaction, staff: discord.Member, note: int, commentaire: str):
    # Vérifie si l'auteur de la commande est un staff
    if not est_staff(interaction.user):
        await interaction.response.send_message("Seuls les membres du staff peuvent laisser un avis.", ephemeral=True)
        return

    if note < 1 or note > 5:
        await interaction.response.send_message("La note doit être entre 1 et 5.", ephemeral=True)
        return

    staff_id = str(staff.id)
    if staff_id not in avis_data:
        avis_data[staff_id] = {"nom": staff.name, "avis": []}

    avis_data[staff_id]["avis"].append({
        "auteur": interaction.user.name,
        "note": note,
        "commentaire": commentaire,
        "date": str(interaction.created_at)
    })
    save_avis(avis_data)
    await interaction.response.send_message(f"Avis enregistré pour {staff.name} : {note}/5 - {commentaire}")

@bot.tree.command(name="voir_avis", description="Voir les avis d'un membre du staff")
async def voir_avis(interaction: discord.Interaction, staff: discord.Member):
    staff_id = str(staff.id)
    if staff_id not in avis_data or not avis_data[staff_id]["avis"]:
        await interaction.response.send_message(f"Aucun avis trouvé pour {staff.name}.", ephemeral=True)
        return

    avis_list = avis_data[staff_id]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)
    embed = discord.Embed(
        title=f"Avis pour {staff.name}",
        color=discord.Color.blue  # <-- Correction : pas de parenthèses
    )
    for avis in avis_list:
        embed.add_field(
            name=f"{avis['auteur']} - {avis['note']}/5",
            value=f"{avis['commentaire']} ({avis['date']})",
            inline=False
        )
    embed.add_field(name="Moyenne", value=f"{moyenne:.2f}/5")
    await interaction.response.send_message(embed=embed)

# Récupérer le token depuis les variables d'environnement
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
