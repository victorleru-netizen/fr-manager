import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading
from discord import app_commands

# Charger les variables d'environnement
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

# Fichiers de stockage
AVIS_FILE = "avis.json"
CONFIG_FILE = "config.json"

def load_avis():
    if os.path.exists(AVIS_FILE):
        try:
            with open(AVIS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_avis(avis):
    with open(AVIS_FILE, "w", encoding="utf-8") as f:
        json.dump(avis, f, indent=4, ensure_ascii=False)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"roles_staff": []}
    return {"roles_staff": []}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

avis_data = load_avis()
config = load_config()

def est_staff(member: discord.Member) -> bool:
    return any(role.id in config["roles_staff"] for role in member.roles)


# ─── SYNCHRONISATION GLOBALE ───
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌍 Synchronisation globale réussie : {len(synced)} commandes enregistrées.")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation : {e}")


# ─── LE FORMULAIRE D'AVIS À 4 CRITÈRES (MODAL) ───
class DetailAvisModal(discord.ui.Modal):
    def __init__(self, staff_member: discord.Member):
        super().__init__(title=f"Avis : {staff_member.display_name}")
        self.staff_member = staff_member

        # Les 4 critères demandés
        self.prof_input = discord.ui.TextInput(
            label="Professionnalisme (Note de 1 à 5)",
            placeholder="Sérieux et respect des procédures",
            required=True,
            min_length=1,
            max_length=1
        )
        self.symp_input = discord.ui.TextInput(
            label="Sympathie & Accueil (Note de 1 à 5)",
            placeholder="Gentillesse et bonne humeur",
            required=True,
            min_length=1,
            max_length=1
        )
        self.rap_input = discord.ui.TextInput(
            label="Rapidité (Note de 1 à 5)",
            placeholder="Prise en charge et efficacité",
            required=True,
            min_length=1,
            max_length=1
        )
        self.ecoute_input = discord.ui.TextInput(
            label="Écoute (Note de 1 à 5)",
            placeholder="Patience et compréhension du problème",
            required=True,
            min_length=1,
            max_length=1
        )
        self.comm_input = discord.ui.TextInput(
            label="Commentaire général",
            style=discord.TextStyle.long,
            placeholder="Exprimez-vous sur votre expérience avec ce staff...",
            required=True,
            max_length=300
        )

        # Ajout des éléments au formulaire
        self.add_item(self.prof_input)
        self.add_item(self.symp_input)
        self.add_item(self.rap_input)
        self.add_item(self.ecoute_input)
        self.add_item(self.comm_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Validation des notes
        try:
            n_prof = int(self.prof_input.value)
            n_symp = int(self.symp_input.value)
            n_rap = int(self.rap_input.value)
            n_ecoute = int(self.ecoute_input.value)
            
            if not all(1 <= n <= 5 for n in [n_prof, n_symp, n_rap, n_ecoute]):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Toutes les notes doivent être des chiffres entiers compris entre 1 et 5.", ephemeral=True)
            return

        # Calcul de la moyenne de cet avis
        note_moyenne_avis = (n_prof + n_symp + n_rap + n_ecoute) / 4

        staff_id = str(self.staff_member.id)
        if staff_id not in avis_data:
            avis_data[staff_id] = {"nom": self.staff_member.name, "avis": []}

        # Sauvegarde des notes détaillées
        avis_data[staff_id]["avis"].append({
            "auteur": interaction.user.name,
            "note": note_moyenne_avis,
            "n_prof": n_prof,
            "n_symp": n_symp,
            "n_rap": n_rap,
            "n_ecoute": n_ecoute,
            "commentaire": self.comm_input.value,
            "date": interaction.created_at.strftime("%d/%m/%Y à %H:%M")
        })
        save_avis(avis_data)

        # Calcul de la moyenne générale globale du staff
        avis_list = avis_data[staff_id]["avis"]
        moyenne_generale = sum(a["note"] for a in avis_list) / len(avis_list)

        # Génération des étoiles pour l'affichage
        e_prof = "⭐" * n_prof
        e_symp = "⭐" * n_symp
        e_rap = "⭐" * n_rap
        e_ecoute = "⭐" * n_ecoute
        
        embed = discord.Embed(
            title="✅ Nouvel Avis Staff Enregistré",
            color=discord.Color.green()
        )
        embed.description = (
            f"**Staff évalué :** {self.staff_member.mention}\n\n"
            f"**📊 Détails des notes :**\n"
            f"💼 Professionnalisme : {e_prof} ({n_prof}/5)\n"
            f"❤️ Sympathie & Accueil : {e_symp} ({n_symp}/5)\n"
            f"⚡ Rapidité : {e_rap} ({n_rap}/5)\n"
            f"👂 Écoute & Patience : {e_ecoute} ({n_ecoute}/5)\n\n"
            f"📈 **Moyenne globale du staff :** {moyenne_generale:.1f} / 5\n\n"
            f"**Commentaire :** *{self.comm_input.value}*"
        )
        
        await interaction.response.send_message(embed=embed)


# ─── SÉLECTION DU STAFF (MENU DÉROULANT) ───
class StaffSelect(discord.ui.Select):
    def __init__(self, membres_staff):
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id), description=f"Noter {m.display_name}")
            for m in membres_staff[:25]
        ]
        super().__init__(placeholder="Sélectionnez le membre du staff à évaluer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        staff_id = int(self.values[0])
        staff_member = interaction.guild.get_member(staff_id)
        
        if not staff_member:
            await interaction.response.send_message("❌ Ce membre du staff ne fait plus partie du serveur.", ephemeral=True)
            return

        # Ouvre le formulaire à 4 critères pour le staff choisi
        await interaction.response.send_modal(DetailAvisModal(staff_member))


class DropdownStaffView(discord.ui.View):
    def __init__(self, membres_staff):
        super().__init__(timeout=60)
        self.add_item(StaffSelect(membres_staff))


class PersistentAvisView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="FAIRE UN AVIS", style=discord.ButtonStyle.success, custom_id="btn_faire_avis", emoji="✍️")
    async def faire_avis_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        membres_staff = [m for m in interaction.guild.members if est_staff(m)]

        if not membres_staff:
            await interaction.response.send_message("❌ Aucun membre de l'équipe n'est disponible ou configuré pour le moment.", ephemeral=True)
            return

        view = DropdownStaffView(membres_staff)
        await interaction.response.send_message("👇 Choisissez le membre du staff que vous souhaitez évaluer :", view=view, ephemeral=True)


# ─── COMMANDES DU BOT ───

@bot.tree.command(name="avis-view", description="Afficher le bouton permanent pour laisser un avis")
async def avis_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent utiliser cette commande.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Évaluation de l'Équipe Staff",
        description=(
            "Votre avis nous intéresse ! Que ce soit suite à un ticket, une aide ou une interaction, "
            "aidez-nous à améliorer la qualité de notre service.\n\n"
            "Cliquez sur le bouton ci-dessous, choisissez votre staff et notez-le sur nos 4 critères de qualité."
        ),
        color=discord.Color.blue()
    )
    
    await interaction.channel.send(embed=embed, view=PersistentAvisView())
    await interaction.response.send_message("✅ Le système d'avis par critères a été installé dans ce salon !", ephemeral=True)


@bot.tree.command(name="avis-config", description="Configurer les rôles autorisés à recevoir des avis")
async def avis_config(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent configurer le bot.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ Configuration des rôles staff",
        description="Cliquez sur le bouton ci-dessous pour ajouter ou retirer des rôles éligibles aux avis.",
        color=discord.Color.blue()
    )

    view = discord.ui.View(timeout=None)
    button = discord.ui.Button(label="Configurer les rôles", style=discord.ButtonStyle.primary, custom_id="config_roles")
    
    async def config_roles_callback(i: discord.Interaction):
        roles = i.guild.roles
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles if role.name != "@everyone"][:25]
        select = discord.ui.Select(placeholder="Sélectionnez les rôles staff...", min_values=1, max_values=len(options), options=options)
        
        async def select_callback(si: discord.Interaction):
            selected_roles = si.data["values"]
            config["roles_staff"] = [int(role_id) for role_id in selected_roles]
            save_config(config)
            roles_names = [i.guild.get_role(int(role_id)).name for role_id in selected_roles]
            embed.description = f"✅ Rôles éligibles aux avis configurés : {', '.join(roles_names)}"
            await si.response.edit_message(embed=embed, view=None)
            
        select.callback = select_callback
        v = discord.ui.View(timeout=None)
        v.add_item(select)
        await i.response.edit_message(embed=embed, v=v)

    button.callback = config_roles_callback
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def staff_autocomplete(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []
    choix = []
    for member in guild.members:
        if any(role.id in config["roles_staff"] for role in member.roles):
            if current.lower() in member.name.lower() or current.lower() in (member.nick or "").lower():
                choix.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
    return choix[:25]


@bot.tree.command(name="voir_avis", description="Voir les avis d'un membre du staff")
@app_commands.autocomplete(staff=staff_autocomplete)
async def voir_avis(interaction: discord.Interaction, staff: str):
    try:
        member = interaction.guild.get_member(int(staff))
        if not member:
            member = await interaction.guild.fetch_member(int(staff))
    except Exception:
        await interaction.response.send_message("❌ Membre introuvable.", ephemeral=True)
        return

    staff_id = str(member.id)
    if staff_id not in avis_data or not avis_data[staff_id]["avis"]:
        embed = discord.Embed(title="❌ Aucun avis trouvé", description=f"Aucun avis n'a été enregistré pour **{member.display_name}**.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    avis_list = avis_data[staff_id]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

    embed = discord.Embed(title=f"📋 Profil de {member.display_name}", color=discord.Color.blue())
    embed.description = f"**Staff :** {member.mention}\n**Moyenne globale :** {moyenne:.1f} / 5\n\n─── **Derniers avis reçus** ───"

    for avis_item in avis_list:
        etoiles = "⭐" * int(round(avis_item['note']))
        embed.add_field(
            name=f"Par {avis_item['auteur']} (le {avis_item['date']})",
            value=f"**Note moyenne :** {etoiles}\n**Commentaire :** *{avis_item['commentaire']}*",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
