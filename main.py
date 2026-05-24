import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading
from discord import app_commands
from datetime import datetime, timedelta

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
            return {}
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

avis_data = load_avis()
config_global = load_config()

# Fonctions utilitaires pour gérer le multi-serveur (Public)
def get_server_config(guild_id: str):
    if guild_id not in config_global:
        config_global[guild_id] = {"roles_staff": [], "salon_affichage": None, "blacklist": []}
    if "blacklist" not in config_global[guild_id]:
        config_global[guild_id]["blacklist"] = []
    return config_global[guild_id]

def est_staff(member: discord.Member) -> bool:
    srv_cfg = get_server_config(str(member.guild.id))
    return any(role.id in srv_cfg.get("roles_staff", []) for role in member.roles)

def est_blacklist(member: discord.Member) -> bool:
    srv_cfg = get_server_config(str(member.guild.id))
    return str(member.id) in srv_cfg.get("blacklist", [])


# ─── SYNCHRONISATION GLOBALE ───
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🌍 Synchronisation globale réussie : {len(synced)} commandes enregistrées.")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation : {e}")


# ─── LE FORMULAIRE D'AVIS À 4 CRITÈRES (MODAL ENRICHI) ───
class DetailAvisModal(discord.ui.Modal):
    def __init__(self, staff_member: discord.Member):
        super().__init__(title=f"Avis : {staff_member.display_name}")
        self.staff_member = staff_member

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
        self.anonyme_input = discord.ui.TextInput(
            label="Rester anonyme public ? (Oui / Non)",
            placeholder="Écrivez 'Oui' pour masquer votre pseudo sur l'avis",
            required=True,
            min_length=2,
            max_length=3,
            default="Non"
        )

        self.add_item(self.prof_input)
        self.add_item(self.symp_input)
        self.add_item(self.rap_input)
        self.add_item(self.ecoute_input)
        self.add_item(self.anonyme_input)

    async def on_submit(self, interaction: discord.Interaction):
        # On demande le commentaire dans une seconde étape car Discord limite à 5 champs maximum par Modal.
        # Pour ne pas perdre les notes, on passe directement à un second Modal pour le commentaire !
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

        est_anonyme = self.anonyme_input.value.strip().lower() in ["oui", "ouis", "y", "yes"]

        # Ouverture du second modal pour obtenir le texte du commentaire
        await interaction.response.send_modal(CommentaireAvisModal(
            self.staff_member, n_prof, n_symp, n_rap, n_ecoute, est_anonyme
        ))


class CommentaireAvisModal(discord.ui.Modal):
    def __init__(self, staff_member: discord.Member, n_prof, n_symp, n_rap, n_ecoute, est_anonyme):
        super().__init__(title="Dernière étape : Votre commentaire")
        self.staff_member = staff_member
        self.n_prof = n_prof
        self.n_symp = n_symp
        self.n_rap = n_rap
        self.n_ecoute = n_ecoute
        self.est_anonyme = est_anonyme

        self.comm_input = discord.ui.TextInput(
            label="Commentaire général",
            style=discord.TextStyle.long,
            placeholder="Exprimez-vous sur votre expérience avec ce staff...",
            required=True,
            max_length=300
        )
        self.add_item(self.comm_input)

    async def on_submit(self, interaction: discord.Interaction):
        note_moyenne_avis = (self.n_prof + self.n_symp + self.n_rap + self.n_ecoute) / 4
        maintenant_str = interaction.created_at.strftime("%d/%m/%Y %H:%M:%S")

        guild_id = str(interaction.guild.id)
        if guild_id not in avis_data:
            avis_data[guild_id] = {}

        staff_id = str(self.staff_member.id)
        if staff_id not in avis_data[guild_id]:
            avis_data[guild_id][staff_id] = {"nom": self.staff_member.name, "avis": []}

        # Sauvegarde complète (les admins gardent l'ID pour la sécurité, mais l'affichage gère l'anonymat)
        avis_data[guild_id][staff_id]["avis"].append({
            "auteur_id": str(interaction.user.id),
            "auteur_nom": interaction.user.name,
            "note": note_moyenne_avis,
            "n_prof": self.n_prof,
            "n_symp": self.n_symp,
            "n_rap": self.n_rap,
            "n_ecoute": self.n_ecoute,
            "commentaire": self.comm_input.value,
            "anonyme": self.est_anonyme,
            "date": maintenant_str
        })
        save_avis(avis_data)

        avis_list = avis_data[guild_id][staff_id]["avis"]
        moyenne_generale = sum(a["note"] for a in avis_list) / len(avis_list)

        e_prof = "⭐" * self.n_prof
        e_symp = "⭐" * self.n_symp
        e_rap = "⭐" * self.n_rap
        e_ecoute = "⭐" * self.n_ecoute
        e_globale = "⭐" * int(round(note_moyenne_avis))
        
        # Gestion de l'affichage de l'auteur
        affichage_auteur = "👤 Membre Anonyme" if self.est_anonyme else interaction.user.mention

        embed = discord.Embed(
            title="✅ Nouvel Avis Staff Enregistré",
            color=discord.Color.green()
        )
        embed.description = (
            f"**Staff évalué :** {self.staff_member.mention}\n\n"
            f"**⭐ NOTE GLOBALE DE L'AVIS : {e_globale} ({note_moyenne_avis:.1f}/5)**\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"**📊 Détails des critères :**\n"
            f"💼 Professionnalisme : {e_prof} ({self.n_prof}/5)\n"
            f"❤️ Sympathie & Accueil : {e_symp} ({self.n_symp}/5)\n"
            f"⚡ Rapidité : {e_rap} ({self.n_rap}/5)\n"
            f"👂 Écoute & Patience : {e_ecoute} ({self.n_ecoute}/5)\n\n"
            f"📈 **Moyenne générale historique du staff :** {moyenne_generale:.1f} / 5\n\n"
            f"**Commentaire :** *{self.comm_input.value}*\n"
            f"*Soumis par : {affichage_auteur}*"
        )
        
        srv_cfg = get_server_config(guild_id)
        salon_id = srv_cfg.get("salon_affichage")
        salon_cible = interaction.guild.get_channel(salon_id) if salon_id else None
        
        if salon_cible:
            try:
                await salon_cible.send(embed=embed)
                await interaction.response.send_message(f"❤️ Merci ! Votre avis a été publié dans {salon_cible.mention}.", ephemeral=True)
            except Exception:
                await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)


# ─── SÉLECTION DU STAFF (MENU DÉROULANT AVEC TIMEOUT 24H) ───
class StaffSelect(discord.ui.Select):
    def __init__(self, membres_staff):
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id), description=f"Noter {m.display_name}")
            for m in membres_staff[:25]
        ]
        super().__init__(placeholder="Sélectionnez le membre du staff à évaluer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if est_blacklist(interaction.user):
            await interaction.response.send_message("❌ Vous avez été banni du système d'avis par un administrateur.", ephemeral=True)
            return

        staff_id = self.values[0]
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        staff_member = interaction.guild.get_member(int(staff_id))
        if not staff_member:
            await interaction.response.send_message("❌ Ce membre du staff ne fait plus partie du serveur.", ephemeral=True)
            return

        # Cooldown 24h
        if guild_id in avis_data and staff_id in avis_data[guild_id]:
            avis_list = avis_data[guild_id][staff_id]["avis"]
            avis_joueur = [a for a in avis_list if a.get("auteur_id") == user_id]
            
            if avis_joueur:
                dernier_avis = avis_joueur[-1]
                try:
                    date_dernier_avis = datetime.strptime(dernier_avis["date"], "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    date_dernier_avis = datetime.strptime(dernier_avis["date"], "%d/%m/%Y à %H:%M")

                temps_ecoule = datetime.utcnow() - date_dernier_avis
                if temps_ecoule < timedelta(hours=24):
                    temps_restant = timedelta(hours=24) - temps_ecoule
                    heures, reste = divmod(temps_restant.seconds, 3600)
                    minutes, _ = divmod(reste, 60)
                    await interaction.response.send_message(
                        f"⏳ **Limite de temps :** Vous avez déjà évalué {staff_member.mention} il y a moins de 24h.\n"
                        f"Veuillez attendre encore **{heures}h et {minutes}min**.", 
                        ephemeral=True
                    )
                    return

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
        if est_blacklist(interaction.user):
            await interaction.response.send_message("❌ Vous avez été banni du système d'avis par un administrateur.", ephemeral=True)
            return

        membres_staff = [m for m in interaction.guild.members if est_staff(m)]
        if not membres_staff:
            await interaction.response.send_message("❌ Aucun membre de l'équipe n'est disponible ou configuré pour le moment.", ephemeral=True)
            return

        view = DropdownStaffView(membres_staff)
        await interaction.response.send_message("👇 Choisissez le membre du staff que vous souhaitez évaluer :", view=view, ephemeral=True)


# ─── CONFIGURATION DES RÔLES ET SALONS ───
class ChannelSelectComponent(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="Étape 2 : Choisissez le salon de publication...", channel_types=[discord.ChannelType.text])

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        salon_choisi = self.values[0]
        srv_cfg = get_server_config(guild_id)
        srv_cfg["salon_affichage"] = salon_choisi.id
        save_config(config_global)
        
        roles_mentions = [interaction.guild.get_role(r_id).mention for r_id in srv_cfg["roles_staff"] if interaction.guild.get_role(r_id)]
        embed = discord.Embed(
            title="⚙️ Configuration Terminée avec Succès !",
            description=f"✅ **Rôles Staff :** {', '.join(roles_mentions) if roles_mentions else 'Aucun'}\n✅ **Salon de publication :** {salon_choisi.mention}\n\nLancez `/avis-view` pour placer le bouton.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ConfigChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ChannelSelectComponent())


class RoleSelectComponent(discord.ui.Select):
    def __init__(self, guild: discord.Guild):
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in guild.roles if role.name != "@everyone"][:25]
        super().__init__(placeholder="Étape 1 : Sélectionnez le ou les rôles staff...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        selected_roles = [int(r_id) for r_id in self.values]
        srv_cfg = get_server_config(guild_id)
        srv_cfg["roles_staff"] = selected_roles
        save_config(config_global)

        embed = discord.Embed(
            title="⚙️ Étape 2 : Salon d'affichage",
            description="Rôles enregistrés ! Choisissez maintenant le salon de réception des avis.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=ConfigChannelView())


class ConfigRolesView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)
        self.add_item(RoleSelectComponent(guild))


class InitialConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Démarrer la configuration", style=discord.ButtonStyle.primary, custom_id="config_start_btn")
    async def config_start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="⚙️ Étape 1 : Rôles du Staff", description="Sélectionnez les rôles définissant votre staff.", color=discord.Color.orange())
        await interaction.response.edit_message(embed=embed, view=ConfigRolesView(interaction.guild))


# ─── COMMANDES DU BOT ───

@bot.tree.command(name="mon-profil", description="Voir mes propres statistiques d'avis (Réservé au staff)")
async def mon_profil(interaction: discord.Interaction):
    if not est_staff(interaction.user):
        await interaction.response.send_message("❌ Cette commande est réservée aux membres de l'équipe staff configurée.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    staff_id = str(interaction.user.id)

    if guild_id not in avis_data or staff_id not in avis_data[guild_id] or not avis_data[guild_id][staff_id]["avis"]:
        await interaction.response.send_message("📊 Vous n'avez pas encore reçu d'avis pour le moment.", ephemeral=True)
        return

    avis_list = avis_data[guild_id][staff_id]["avis"]
    total = len(avis_list)
    
    m_globale = sum(a["note"] for a in avis_list) / total
    m_prof = sum(a["n_prof"] for a in avis_list) / total
    m_symp = sum(a["n_symp"] for a in avis_list) / total
    m_rap = sum(a["n_rap"] for a in avis_list) / total
    m_ecoute = sum(a["n_ecoute"] for a in avis_list) / total

    embed = discord.Embed(title=f"📊 Votre Profil Staff - {interaction.user.display_name}", color=discord.Color.teal())
    embed.description = (
        f"**Moyenne globale :** {'⭐' * int(round(m_globale))} ({m_globale:.2f}/5)\n"
        f"**Nombre total d'avis :** 💬 {total}\n\n"
        f"**📈 Détails par critères :**\n"
        f"💼 Professionnalisme : {m_prof:.1f}/5\n"
        f"❤️ Sympathie & Accueil : {m_symp:.1f}/5\n"
        f"⚡ Rapidité : {m_rap:.1f}/5\n"
        f"👂 Écoute & Patience : {m_ecoute:.1f}/5"
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="top-staff", description="Afficher le TOP 3 des staffs les mieux notés du serveur")
async def top_staff(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or not avis_data[guild_id]:
        await interaction.response.send_message("❌ Aucun avis n'a encore été enregistré sur ce serveur.", ephemeral=True)
        return

    scores = []
    for s_id, s_data in avis_data[guild_id].items():
        if s_data["avis"]:
            moy = sum(a["note"] for a in s_data["avis"]) / len(s_data["avis"])
            scores.append((s_id, s_data["nom"], moy, len(s_data["avis"])))

    scores.sort(key=lambda x: (x[2], x[3]), reverse=True)
    top_3 = scores[:3]

    if not top_3:
        await interaction.response.send_message("❌ Aucun classement disponible.", ephemeral=True)
        return

    embed = discord.Embed(title="🏆 TOP 3 - Équipe Staff du Serveur", color=discord.Color.gold())
    medailles = ["🥇", "🥈", "🥉"]
    
    desc = ""
    for i, (s_id, nom, moy, count) in enumerate(top_3):
        mention = f"<@{s_id}>"
        desc += f"{medailles[i]} **{nom}** ({mention})\n┗ Score : **{moy:.1f}/5** ({count} avis)\n\n"
    
    embed.description = desc
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avis-stats", description="Voir le classement complet de toute l'équipe staff (Admin)")
async def avis_stats(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent voir les statistiques globales.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or not avis_data[guild_id]:
        await interaction.response.send_message("❌ Aucune donnée d'avis enregistrée.", ephemeral=True)
        return

    scores = []
    for s_id, s_data in avis_data[guild_id].items():
        if s_data["avis"]:
            moy = sum(a["note"] for a in s_data["avis"]) / len(s_data["avis"])
            scores.append((s_data["nom"], moy, len(s_data["avis"])))

    scores.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="📊 Classement Général Interne du Staff", color=discord.Color.purple())
    desc = ""
    for idx, (nom, moy, count) in enumerate(scores, start=1):
        desc += f"**#{idx} {nom}** — **{moy:.2f}/5** ({count} avis)\n"
    
    embed.description = desc
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="avis-blacklist", description="Ajouter ou retirer un membre du système d'avis (Admin)")
@app_commands.choices(action=[
    app_commands.Choice(name="Ajouter (Bloquer)", value="add"),
    app_commands.Choice(name="Retirer (Débloquer)", value="remove")
])
async def avis_blacklist(interaction: discord.Interaction, action: str, membre: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent gérer la blacklist.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    srv_cfg = get_server_config(guild_id)
    m_id = str(membre.id)

    if action == "add":
        if m_id not in srv_cfg["blacklist"]:
            srv_cfg["blacklist"].append(m_id)
            save_config(config_global)
            await interaction.response.send_message(f"✅ {membre.mention} a été ajouté à la blacklist et ne peut plus soumettre d'avis.", ephemeral=True)
        else:
            await interaction.response.send_message(f"ℹ️ {membre.display_name} est déjà blacklisté.", ephemeral=True)
    elif action == "remove":
        if m_id in srv_cfg["blacklist"]:
            srv_cfg["blacklist"].remove(m_id)
            save_config(config_global)
            await interaction.response.send_message(f"✅ {membre.mention} a été retiré de la blacklist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"ℹ️ {membre.display_name} n'est pas dans la blacklist.", ephemeral=True)


@bot.tree.command(name="avis-clear", description="Réinitialiser les avis d'un staff ou de tout le serveur (Admin)")
async def avis_clear(interaction: discord.Interaction, staff: discord.Member = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent effacer les avis.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or not avis_data[guild_id]:
        await interaction.response.send_message("❌ Aucun avis à effacer pour ce serveur.", ephemeral=True)
        return

    if staff:
        staff_id = str(staff.id)
        if staff_id in avis_data[guild_id]:
            del avis_data[guild_id][staff_id]
            save_avis(avis_data)
            await interaction.response.send_message(f"🗑️ Tous les avis concernant **{staff.display_name}** ont été supprimés.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Aucun avis trouvé pour {staff.display_name}.", ephemeral=True)
    else:
        avis_data[guild_id] = {}
        save_avis(avis_data)
        await interaction.response.send_message("🗑️ **Réinitialisation complète réussie.** Tous les avis du serveur ont été purgés.", ephemeral=True)


@bot.tree.command(name="avis-view", description="Afficher le bouton permanent pour laisser un avis")
async def avis_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent utiliser cette commande.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Évaluation de l'Équipe Staff",
        description="Votre avis nous intéresse ! Cliquez sur le bouton ci-dessous, choisissez votre staff et notez-le.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=PersistentAvisView())
    await interaction.response.send_message("✅ Le système d'avis par critères a été installé dans ce salon !", ephemeral=True)


@bot.tree.command(name="avis-config", description="Configurer les rôles et le salon d'affichage des avis")
async def avis_config(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent configurer le bot.", ephemeral=True)
        return

    embed = discord.Embed(title="⚙️ Configuration du Système d'Avis", description="Cliquez sur le bouton ci-dessous pour configurer le bot pas-à-pas.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=InitialConfigView(), ephemeral=True)


async def staff_autocomplete(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []
    guild_id = str(guild.id)
    srv_cfg = get_server_config(guild_id)
    
    choix = []
    for member in guild.members:
        if any(role.id in srv_cfg.get("roles_staff", []) for role in member.roles):
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

    guild_id = str(interaction.guild.id)
    if guild_id not in avis_data or str(member.id) not in avis_data[guild_id] or not avis_data[guild_id][str(member.id)]["avis"]:
        embed = discord.Embed(title="❌ Aucun avis trouvé", description=f"Aucun avis n'a été enregistré pour **{member.display_name}**.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    avis_list = avis_data[guild_id][str(member.id)]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

    embed = discord.Embed(title=f"📋 Profil de {member.display_name}", color=discord.Color.blue())
    embed.description = f"**Staff :** {member.mention}\n**Moyenne globale historique :** {moyenne:.1f} / 5\n\n─── **Derniers avis reçus** ───"

    for avis_item in avis_list:
        etoiles = "⭐" * int(round(avis_item['note']))
        
        # Masquage du pseudo si l'avis est marqué comme anonyme
        nom_auteur = "👤 Anonyme" if avis_item.get("anonyme", False) else avis_item.get("auteur_nom", "Anonyme")
        
        embed.add_field(
            name=f"Par {nom_auteur} (le {avis_item['date']})",
            value=f"**Note moyenne :** {etoiles} ({avis_item['note']:.1f}/5)\n**Commentaire :** *{avis_item['commentaire']}*",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
