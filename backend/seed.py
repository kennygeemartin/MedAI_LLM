"""Import short source-based drafts. Publication always requires admin review."""
from sqlalchemy import select
from backend.database import Session, User, Document, Audit

ARTICLES = [
    ('Understanding malaria', 'Malaria', 'https://www.who.int/news-room/fact-sheets/detail/malaria',
     'Malaria is a parasitic infection usually transmitted by infected mosquitoes. Early illness can involve headache, chills, and fever. These symptoms overlap with other illnesses, so testing is important. People with severe illness need emergency care. Young children and pregnant people are among those at greater risk. Sleeping under mosquito nets and reducing mosquito bites help prevent infection.'),
    ('Understanding high blood pressure', 'Hypertension', 'https://www.who.int/news-room/fact-sheets/detail/hypertension',
     'High blood pressure can be present without noticeable symptoms. Blood pressure measurement is needed to detect it. Untreated hypertension can damage the heart, kidneys, and other organs. Healthier food choices, less dietary salt, physical activity, and avoiding tobacco can support blood pressure control. Some people also need clinician-managed medicine.'),
    ('Understanding diabetes', 'Diabetes', 'https://www.who.int/news-room/fact-sheets/detail/diabetes',
     'Diabetes affects how the body controls blood glucose. Possible signs include unusual thirst, frequent urination, tiredness, blurred vision, and unexplained weight loss. Type 2 diabetes may develop with mild symptoms over years. Healthcare check-ups and blood tests support early detection. Healthy eating and regular movement can help prevent or delay type 2 diabetes; management may also require medication and regular monitoring.'),
    ('Everyday healthy eating', 'Nutrition', 'https://www.who.int/news-room/fact-sheets/detail/healthy-diet',
     'A varied diet supports health. Include vegetables, fruit, pulses, and whole grains, and reduce foods high in salt, free sugars, and unhealthy fats. Appropriate food choices depend on age, activity, individual needs, and locally available foods. A healthcare professional can help adapt nutrition advice for a medical condition.'),
    ('Care during pregnancy and after birth', 'Maternal health', 'https://www.who.int/health-topics/maternal-health',
     'Maternal healthcare covers pregnancy, childbirth, and the period after birth. Good-quality care and support help protect both parent and baby. Skilled healthcare professionals can identify and manage complications. Arrange pregnancy and postnatal care with a qualified healthcare service, and discuss any concerns promptly.'),
    ('Understanding vaccination', 'Immunization', 'https://www.who.int/news-room/questions-and-answers/item/vaccines-and-immunization-what-is-vaccination',
     'Vaccination prepares the immune system to protect against specific infections. Vaccines help reduce the risk of disease and its complications. Ask your healthcare provider which vaccines are appropriate and when they are due. Bring your immunization record to appointments. This article does not provide a Nigerian vaccination schedule; confirm the current local schedule with your clinic.'),
]

def main():
    with Session() as db:
        admin = db.scalar(select(User).where(User.role == 'admin', User.active.is_(True)).order_by(User.id))
        if not admin:
            raise SystemExit('Create an administrator first: python -m backend.manage create-admin')
        added = 0
        for title, category, source, content in ARTICLES:
            if not db.scalar(select(Document).where(Document.source == source)):
                db.add(Document(title=title, category=category, source=source, content=content, approved=False, uploaded_by=admin.id))
                added += 1
        db.add(Audit(user_id=admin.id, action=f'CLI imported {added} source-based draft articles'))
        db.commit()
    print(f'Imported {added} drafts. Review and publish them in Administration > Knowledge.')

if __name__ == '__main__':
    main()
